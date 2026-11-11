from dataclasses import dataclass, field

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import get_conn
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class Admin:
    id: int
    username: str
    role: str
    permissions: list[str] = field(default_factory=list)
    allowed_brands: list[int] = field(default_factory=list)

    def can(self, perm: str) -> bool:
        return "*" in self.permissions or perm in self.permissions


def current_admin(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn=Depends(get_conn),
) -> Admin:
    if cred is None:
        raise HTTPException(401, "Not logged in")
    admin_id = decode_token(cred.credentials, "access")
    if admin_id is None:
        raise HTTPException(401, "Invalid or expired token")
    row = conn.execute(
        """SELECT a.id, a.username, r.name AS role, r.permissions, a.allowed_brands
           FROM admin_users a JOIN admin_roles r ON r.id = a.role_id
           WHERE a.id = %s AND a.is_active""",
        (admin_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(401, "Account disabled")
    return Admin(**row)


def require(perm: str):
    def checker(admin: Admin = Depends(current_admin)) -> Admin:
        if not admin.can(perm):
            raise HTTPException(403, f"Missing permission: {perm}")
        return admin

    return checker


def brand_scope(admin: Admin, brand_id: int | None) -> list[int]:
    """Brands this request may touch. Every query must filter by this list."""
    if brand_id is None:
        return list(admin.allowed_brands)
    if brand_id not in admin.allowed_brands:
        raise HTTPException(403, "No access to this brand")
    return [brand_id]


def paging(page: int, size: int, max_size: int = 500) -> tuple[int, int]:
    page = max(page, 1)
    size = min(max(size, 1), max_size)
    return size, (page - 1) * size
