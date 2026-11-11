from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import audit
from ..config import settings
from ..db import get_conn
from ..deps import Admin, current_admin
from ..security import create_token, decode_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str
    otp: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str


class OtpIn(BaseModel):
    code: str


def _tokens(admin_id: int) -> dict:
    return {
        "access_token": create_token(admin_id, "access"),
        "refresh_token": create_token(admin_id, "refresh"),
        "token_type": "bearer",
    }


def _verify_otp(secret: str | None, code: str | None) -> bool:
    return bool(secret and code) and pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=1)


@router.post("/login")
def login(body: LoginIn, conn=Depends(get_conn)):
    row = conn.execute(
        """SELECT id, password_hash, is_active, totp_enabled, totp_secret, failed_logins, locked_until
           FROM admin_users WHERE username = %s FOR UPDATE""",
        (body.username,),
    ).fetchone()
    now = datetime.now(timezone.utc)
    if row and row["locked_until"] and row["locked_until"] > now:
        minutes = int((row["locked_until"] - now).total_seconds() // 60) + 1
        raise HTTPException(423, f"Too many failed attempts. Try again in {minutes} minute(s).")

    ok = row is not None and row["is_active"] and verify_password(body.password, row["password_hash"])
    if ok and row["totp_enabled"]:
        if not body.otp:
            # password is right; the UI now asks for the 6-digit code (not counted as a failure)
            raise HTTPException(401, "OTP_REQUIRED")
        ok = _verify_otp(row["totp_secret"], body.otp)

    if not ok:
        if row is not None:
            fails = row["failed_logins"] + 1
            lock = now + timedelta(minutes=settings.lock_minutes) if fails >= settings.max_failed_logins else None
            conn.execute("UPDATE admin_users SET failed_logins = %s, locked_until = %s WHERE id = %s",
                         (0 if lock else fails, lock, row["id"]))
            audit.log(conn, row["id"], "auth.login_failed", None, {"locked": bool(lock)})
            conn.commit()  # keep the counter even though we raise
        raise HTTPException(401, "Wrong username, password or code")

    conn.execute("UPDATE admin_users SET failed_logins = 0, locked_until = NULL, last_login_at = now()"
                 " WHERE id = %s", (row["id"],))
    audit.log(conn, row["id"], "auth.login")
    return _tokens(row["id"])


@router.post("/refresh")
def refresh(body: RefreshIn, conn=Depends(get_conn)):
    admin_id = decode_token(body.refresh_token, "refresh")
    if admin_id is None:
        raise HTTPException(401, "Invalid or expired refresh token")
    row = conn.execute("SELECT is_active FROM admin_users WHERE id = %s", (admin_id,)).fetchone()
    if row is None or not row["is_active"]:
        raise HTTPException(401, "Account disabled")
    return _tokens(admin_id)


@router.get("/me")
def me(admin: Admin = Depends(current_admin), conn=Depends(get_conn)):
    extra = conn.execute("SELECT totp_enabled FROM admin_users WHERE id = %s", (admin.id,)).fetchone()
    return {**admin.__dict__, **extra}


# ------------------------------------------------------------------ two-factor (TOTP)
@router.post("/2fa/setup")
def setup_2fa(admin: Admin = Depends(current_admin), conn=Depends(get_conn)):
    """Create a new secret. It only becomes active after /2fa/enable with a valid code."""
    row = conn.execute("SELECT totp_enabled FROM admin_users WHERE id = %s", (admin.id,)).fetchone()
    if row["totp_enabled"]:
        raise HTTPException(400, "2FA is already enabled")
    secret = pyotp.random_base32()
    conn.execute("UPDATE admin_users SET totp_secret = %s WHERE id = %s", (secret, admin.id))
    uri = pyotp.TOTP(secret).provisioning_uri(name=admin.username, issuer_name=settings.totp_issuer)
    return {"secret": secret, "otpauth_uri": uri}


@router.post("/2fa/enable")
def enable_2fa(body: OtpIn, admin: Admin = Depends(current_admin), conn=Depends(get_conn)):
    row = conn.execute("SELECT totp_secret FROM admin_users WHERE id = %s", (admin.id,)).fetchone()
    if not _verify_otp(row["totp_secret"], body.code):
        raise HTTPException(400, "Wrong code. Check the time on your phone and try again.")
    conn.execute("UPDATE admin_users SET totp_enabled = true WHERE id = %s", (admin.id,))
    audit.log(conn, admin.id, "auth.2fa_enabled", admin.id)
    return {"totp_enabled": True}


@router.post("/2fa/disable")
def disable_2fa(body: OtpIn, admin: Admin = Depends(current_admin), conn=Depends(get_conn)):
    row = conn.execute("SELECT totp_secret, totp_enabled FROM admin_users WHERE id = %s", (admin.id,)).fetchone()
    if not row["totp_enabled"]:
        return {"totp_enabled": False}
    if not _verify_otp(row["totp_secret"], body.code):
        raise HTTPException(400, "Wrong code")
    conn.execute("UPDATE admin_users SET totp_enabled = false, totp_secret = NULL WHERE id = %s", (admin.id,))
    audit.log(conn, admin.id, "auth.2fa_disabled", admin.id)
    return {"totp_enabled": False}
