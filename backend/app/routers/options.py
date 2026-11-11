from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..deps import Admin, brand_scope, current_admin, require

router = APIRouter(prefix="/api", tags=["options"])


@router.get("/options")
def options(admin: Admin = Depends(current_admin), conn=Depends(get_conn)):
    brands = admin.allowed_brands
    q = lambda sql: conn.execute(sql, (brands,)).fetchall()  # noqa: E731
    return {
        "brands": q("SELECT id, name, currency FROM brands WHERE id = ANY(%s) ORDER BY id"),
        "vip_levels": q("SELECT id, brand_id, level, name FROM vip_levels WHERE brand_id = ANY(%s)"
                        " ORDER BY brand_id, level"),
        "member_levels": q("SELECT id, brand_id, name, sort FROM member_levels WHERE brand_id = ANY(%s)"
                           " ORDER BY brand_id, sort"),
        "sources": q("SELECT id, brand_id, code, name, is_active FROM traffic_sources WHERE brand_id = ANY(%s)"
                     " ORDER BY brand_id, name"),
        "tags": q("SELECT id, brand_id, name FROM tags WHERE brand_id = ANY(%s) ORDER BY brand_id, name"),
        "statuses": ["normal", "blacklist", "leaving", "left"],
        "account_types": ["formal", "test"],
    }


# ------------------------------------------------------------------ traffic sources
class SourceIn(BaseModel):
    brand_id: int
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=100)


class SourcePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


@router.post("/sources", status_code=201)
def create_source(body: SourceIn, admin: Admin = Depends(require("source.manage")), conn=Depends(get_conn)):
    brand_scope(admin, body.brand_id)
    row = conn.execute(
        """INSERT INTO traffic_sources (brand_id, code, name) VALUES (%s, %s, %s)
           ON CONFLICT (brand_id, code) DO NOTHING RETURNING *""",
        (body.brand_id, body.code, body.name),
    ).fetchone()
    if row is None:
        raise HTTPException(409, "Code already exists in this brand")
    audit.log(conn, admin.id, "source.create", row["id"], body.model_dump())
    return row


@router.patch("/sources/{source_id}")
def update_source(source_id: int, body: SourcePatch, admin: Admin = Depends(require("source.manage")),
                  conn=Depends(get_conn)):
    changes = body.model_dump(exclude_none=True)
    row = conn.execute("SELECT * FROM traffic_sources WHERE id = %s AND brand_id = ANY(%s)",
                       (source_id, admin.allowed_brands)).fetchone()
    if row is None:
        raise HTTPException(404, "Source not found")
    if changes:
        sets = ", ".join(f"{k} = %({k})s" for k in changes)
        row = conn.execute(f"UPDATE traffic_sources SET {sets} WHERE id = %(id)s RETURNING *",
                           {**changes, "id": source_id}).fetchone()
        audit.log(conn, admin.id, "source.update", source_id, changes)
    return row
