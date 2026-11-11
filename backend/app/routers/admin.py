from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..deps import Admin, paging, require
from ..security import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.]+$")
    password: str = Field(min_length=8)
    role_id: int
    allowed_brands: list[int] = []


class AdminPatch(BaseModel):
    password: str | None = Field(default=None, min_length=8)
    role_id: int | None = None
    allowed_brands: list[int] | None = None
    is_active: bool | None = None


def _check_brands(admin: Admin, brands: list[int]):
    # you can only hand out brands you have yourself
    if not set(brands) <= set(admin.allowed_brands):
        raise HTTPException(403, "Cannot grant brands you do not have")


@router.get("/roles")
def roles(admin: Admin = Depends(require("admin.manage")), conn=Depends(get_conn)):
    return conn.execute("SELECT * FROM admin_roles ORDER BY id").fetchall()


@router.get("/users")
def users(admin: Admin = Depends(require("admin.manage")), conn=Depends(get_conn)):
    return conn.execute(
        """SELECT a.id, a.username, a.role_id, r.name AS role, a.allowed_brands, a.is_active, a.created_at
           FROM admin_users a JOIN admin_roles r ON r.id = a.role_id ORDER BY a.id"""
    ).fetchall()


@router.post("/users", status_code=201)
def create_user(body: AdminCreate, admin: Admin = Depends(require("admin.manage")), conn=Depends(get_conn)):
    _check_brands(admin, body.allowed_brands)
    if conn.execute("SELECT 1 FROM admin_users WHERE username = %s", (body.username,)).fetchone():
        raise HTTPException(409, "Username already exists")
    row = conn.execute(
        """INSERT INTO admin_users (username, password_hash, role_id, allowed_brands)
           VALUES (%s, %s, %s, %s) RETURNING id, username, role_id, allowed_brands, is_active""",
        (body.username, hash_password(body.password), body.role_id, body.allowed_brands),
    ).fetchone()
    audit.log(conn, admin.id, "admin.create", row["id"],
              {"username": body.username, "role_id": body.role_id, "brands": body.allowed_brands})
    return row


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: AdminPatch, admin: Admin = Depends(require("admin.manage")),
                conn=Depends(get_conn)):
    if conn.execute("SELECT 1 FROM admin_users WHERE id = %s", (user_id,)).fetchone() is None:
        raise HTTPException(404, "Admin not found")
    if user_id == admin.id and body.is_active is False:
        raise HTTPException(400, "You cannot disable yourself")
    changes = {}
    if body.password:
        changes["password_hash"] = hash_password(body.password)
    if body.role_id is not None:
        changes["role_id"] = body.role_id
    if body.allowed_brands is not None:
        _check_brands(admin, body.allowed_brands)
        changes["allowed_brands"] = body.allowed_brands
    if body.is_active is not None:
        changes["is_active"] = body.is_active
    if changes:
        sets = ", ".join(f"{k} = %({k})s" for k in changes)
        conn.execute(f"UPDATE admin_users SET {sets} WHERE id = %(id)s", {**changes, "id": user_id})
    audit.log(conn, admin.id, "admin.update", user_id,
              {k: v for k, v in body.model_dump(exclude_none=True).items() if k != "password"}
              | ({"password": "changed"} if body.password else {}))
    return {"id": user_id, "updated": list(changes)}


@router.get("/audit-logs")
def audit_logs(action: str | None = None, admin_username: str | None = None, target_id: int | None = None,
               page: int = 1, size: int = 50,
               admin: Admin = Depends(require("audit.view")), conn=Depends(get_conn)):
    limit, offset = paging(page, size)
    w, p = ["true"], {}
    if action:
        w.append("l.action LIKE %(action)s")
        p["action"] = action + "%"
    if admin_username:
        w.append("a.username = %(au)s")
        p["au"] = admin_username
    if target_id:
        w.append("l.target_id = %(tid)s")
        p["tid"] = target_id
    where = " AND ".join(w)
    base = "FROM audit_logs l LEFT JOIN admin_users a ON a.id = l.admin_id"
    total = conn.execute(f"SELECT count(*) AS n {base} WHERE {where}", p).fetchone()["n"]
    rows = conn.execute(
        f"SELECT l.*, a.username AS admin_name {base} WHERE {where} ORDER BY l.id DESC"
        " LIMIT %(limit)s OFFSET %(offset)s",
        {**p, "limit": limit, "offset": offset},
    ).fetchall()
    return {"total": total, "rows": rows}
