from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import audit
from ..db import get_conn
from ..deps import Admin, current_admin
from ..security import create_token, decode_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


def _tokens(admin_id: int) -> dict:
    return {
        "access_token": create_token(admin_id, "access"),
        "refresh_token": create_token(admin_id, "refresh"),
        "token_type": "bearer",
    }


@router.post("/login")
def login(body: LoginIn, conn=Depends(get_conn)):
    row = conn.execute(
        "SELECT id, password_hash, is_active FROM admin_users WHERE username = %s",
        (body.username,),
    ).fetchone()
    if row is None or not row["is_active"] or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Wrong username or password")
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
def me(admin: Admin = Depends(current_admin)):
    return admin.__dict__
