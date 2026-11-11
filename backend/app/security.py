from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # placeholder / malformed hash
        return False


def create_token(admin_id: int, kind: str) -> str:
    now = datetime.now(timezone.utc)
    if kind == "access":
        exp = now + timedelta(minutes=settings.access_minutes)
    else:
        exp = now + timedelta(days=settings.refresh_days)
    payload = {"sub": str(admin_id), "kind": kind, "iat": now, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, kind: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("kind") != kind:
        return None
    return int(payload["sub"])
