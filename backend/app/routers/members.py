import io
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel, Field

from .. import audit
from ..config import settings
from ..db import get_conn
from ..deps import Admin, brand_scope, current_admin, paging, require

router = APIRouter(prefix="/api/members", tags=["members"])

Status = Literal["normal", "blacklist", "leaving", "left"]

SELECT_MEMBER = """
SELECT m.id, m.brand_id, b.name AS brand_name, m.username, m.full_name, m.phone,
       m.status, m.depth, m.path, v.level AS vip_level, v.name AS vip_name,
       inv.id AS inviter_id, inv.username AS inviter_username,
       top.id AS top_agent_id, top.username AS top_agent_username,
       b.currency, COALESCE(w.balance, 0) AS balance, COALESCE(w.frozen, 0) AS frozen,
       m.created_at
FROM members m
JOIN brands b          ON b.id = m.brand_id
LEFT JOIN vip_levels v ON v.id = m.vip_level_id
LEFT JOIN members inv  ON inv.id = m.inviter_id
LEFT JOIN members top  ON m.depth > 0 AND top.id = split_part(m.path, '/', 2)::bigint
LEFT JOIN wallets w    ON w.member_id = m.id
"""


class MemberFilter:
    def __init__(
        self,
        brand_id: int | None = None,
        username: str | None = None,
        username_like: str | None = None,
        status: Status | None = None,
        vip_level: int | None = None,
        inviter: str | None = None,
        top_agent_id: int | None = None,
        tag_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        self.__dict__.update(locals())
        del self.__dict__["self"]

    def where(self, admin: Admin) -> tuple[str, dict]:
        p: dict = {"brands": brand_scope(admin, self.brand_id)}
        w = ["m.brand_id = ANY(%(brands)s)"]
        if self.username:
            w.append("m.username = %(username)s")
            p["username"] = self.username.strip()
        if self.username_like:
            w.append("m.username ILIKE %(ulike)s")
            p["ulike"] = f"%{self.username_like.strip()}%"
        if self.status:
            w.append("m.status = %(status)s")
            p["status"] = self.status
        if self.vip_level is not None:
            w.append("m.vip_level_id IN (SELECT id FROM vip_levels WHERE level = %(vip)s)")
            p["vip"] = self.vip_level
        if self.inviter:
            w.append("m.inviter_id IN (SELECT id FROM members WHERE username = %(inviter)s"
                     " AND brand_id = ANY(%(brands)s))")
            p["inviter"] = self.inviter.strip()
        if self.top_agent_id:
            w.append("m.path LIKE %(top_path)s")
            p["top_path"] = f"/{self.top_agent_id}/%"
        if self.tag_id:
            w.append("EXISTS (SELECT 1 FROM member_tags t WHERE t.member_id = m.id AND t.tag_id = %(tag)s)")
            p["tag"] = self.tag_id
        if self.date_from:
            w.append("m.created_at >= %(dfrom)s")
            p["dfrom"] = self.date_from
        if self.date_to:
            w.append("m.created_at < %(dto)s")
            p["dto"] = self.date_to + timedelta(days=1)
        return " AND ".join(w), p


def get_member(conn, admin: Admin, member_id: int, lock: bool = False) -> dict:
    row = conn.execute(
        "SELECT * FROM members WHERE id = %s AND brand_id = ANY(%s)" + (" FOR UPDATE" if lock else ""),
        (member_id, admin.allowed_brands),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Member not found")
    return row


@router.get("")
def list_members(
    f: MemberFilter = Depends(),
    page: int = 1,
    size: int = 100,
    admin: Admin = Depends(require("member.view")),
    conn=Depends(get_conn),
):
    limit, offset = paging(page, size)
    where, p = f.where(admin)
    total = conn.execute(f"SELECT count(*) AS n FROM members m WHERE {where}", p).fetchone()["n"]
    rows = conn.execute(
        f"{SELECT_MEMBER} WHERE {where} ORDER BY m.created_at DESC, m.id DESC"
        " LIMIT %(limit)s OFFSET %(offset)s",
        {**p, "limit": limit, "offset": offset},
    ).fetchall()
    return {"total": total, "rows": rows}


@router.get("/export")
def export_members(
    f: MemberFilter = Depends(),
    admin: Admin = Depends(require("member.export")),
    conn=Depends(get_conn),
):
    where, p = f.where(admin)
    rows = conn.execute(
        f"{SELECT_MEMBER} WHERE {where} ORDER BY m.created_at DESC LIMIT %(limit)s",
        {**p, "limit": settings.export_max_rows},
    ).fetchall()
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("members")
    cols = ["id", "brand_name", "username", "full_name", "phone", "status", "vip_name",
            "inviter_username", "top_agent_username", "currency", "balance", "frozen", "created_at"]
    ws.append(cols)
    for r in rows:
        ws.append([r[c].replace(tzinfo=None) if c == "created_at" else r[c] for c in cols])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    audit.log(conn, admin.id, "member.export", None, {"rows": len(rows), "filter": {
        k: str(v) for k, v in f.__dict__.items() if v is not None}})
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="members.xlsx"'},
    )


class MemberCreate(BaseModel):
    brand_id: int
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.]+$")
    full_name: str | None = None
    phone: str | None = None
    inviter_username: str | None = None


@router.post("", status_code=201)
def create_member(body: MemberCreate, admin: Admin = Depends(require("member.edit")), conn=Depends(get_conn)):
    brand_scope(admin, body.brand_id)
    if conn.execute("SELECT 1 FROM members WHERE brand_id = %s AND username = %s",
                    (body.brand_id, body.username)).fetchone():
        raise HTTPException(409, "Username already exists in this brand")
    inviter = None
    if body.inviter_username:
        inviter = conn.execute("SELECT id, path, depth FROM members WHERE brand_id = %s AND username = %s",
                               (body.brand_id, body.inviter_username)).fetchone()
        if inviter is None:
            raise HTTPException(400, "Inviter not found in this brand")
    vip0 = conn.execute("SELECT id FROM vip_levels WHERE brand_id = %s ORDER BY level LIMIT 1",
                        (body.brand_id,)).fetchone()
    row = conn.execute(
        """INSERT INTO members (brand_id, username, full_name, phone, vip_level_id, inviter_id, depth)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (body.brand_id, body.username, body.full_name, body.phone, vip0["id"] if vip0 else None,
         inviter["id"] if inviter else None, inviter["depth"] + 1 if inviter else 0),
    ).fetchone()
    path = (inviter["path"] if inviter else "/") + f"{row['id']}/"
    conn.execute("UPDATE members SET path = %s WHERE id = %s", (path, row["id"]))
    conn.execute("INSERT INTO wallets (member_id) VALUES (%s)", (row["id"],))
    audit.log(conn, admin.id, "member.create", row["id"], body.model_dump())
    return conn.execute(f"{SELECT_MEMBER} WHERE m.id = %s", (row["id"],)).fetchone()


@router.get("/{member_id}")
def member_detail(member_id: int, admin: Admin = Depends(require("member.view")), conn=Depends(get_conn)):
    m = get_member(conn, admin, member_id)
    row = conn.execute(f"{SELECT_MEMBER} WHERE m.id = %s", (member_id,)).fetchone()
    row["tags"] = conn.execute(
        "SELECT t.id, t.name FROM member_tags mt JOIN tags t ON t.id = mt.tag_id WHERE mt.member_id = %s",
        (member_id,),
    ).fetchall()
    row["direct_invites"] = conn.execute(
        "SELECT count(*) AS n FROM members WHERE inviter_id = %s", (member_id,)).fetchone()["n"]
    row["downline_total"] = conn.execute(
        "SELECT count(*) AS n FROM members WHERE path LIKE %s AND id <> %s", (m["path"] + "%", member_id)
    ).fetchone()["n"]
    return row


@router.get("/{member_id}/children")
def member_children(member_id: int, page: int = 1, size: int = 200,
                    admin: Admin = Depends(require("member.view")), conn=Depends(get_conn)):
    get_member(conn, admin, member_id)
    limit, offset = paging(page, size)
    rows = conn.execute(
        """SELECT m.id, m.username, m.status, m.depth,
                  (SELECT count(*) FROM members c WHERE c.inviter_id = m.id) AS children
           FROM members m WHERE m.inviter_id = %s ORDER BY m.id LIMIT %s OFFSET %s""",
        (member_id, limit, offset),
    ).fetchall()
    return {"rows": rows}


@router.get("/{member_id}/downline")
def member_downline(member_id: int, page: int = 1, size: int = 100,
                    admin: Admin = Depends(require("member.view")), conn=Depends(get_conn)):
    m = get_member(conn, admin, member_id)
    limit, offset = paging(page, size)
    p = (m["path"] + "%", member_id)
    total = conn.execute("SELECT count(*) AS n FROM members m WHERE m.path LIKE %s AND m.id <> %s", p
                         ).fetchone()["n"]
    rows = conn.execute(
        f"{SELECT_MEMBER} WHERE m.path LIKE %s AND m.id <> %s ORDER BY m.depth, m.id LIMIT %s OFFSET %s",
        (*p, limit, offset),
    ).fetchall()
    return {"total": total, "rows": rows}


class StatusIn(BaseModel):
    status: Status
    note: str | None = None


@router.patch("/{member_id}/status")
def change_status(member_id: int, body: StatusIn, admin: Admin = Depends(require("member.edit")),
                  conn=Depends(get_conn)):
    m = get_member(conn, admin, member_id, lock=True)
    conn.execute("UPDATE members SET status = %s, updated_at = now() WHERE id = %s", (body.status, member_id))
    audit.log(conn, admin.id, "member.status_change", member_id,
              {"from": m["status"], "to": body.status, "note": body.note})
    return {"id": member_id, "status": body.status}


class BulkStatusIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=1000)
    status: Status
    note: str | None = None


@router.post("/bulk-status")
def bulk_status(body: BulkStatusIn, admin: Admin = Depends(require("member.edit")), conn=Depends(get_conn)):
    rows = conn.execute(
        """UPDATE members SET status = %s, updated_at = now()
           WHERE id = ANY(%s) AND brand_id = ANY(%s) RETURNING id""",
        (body.status, body.ids, admin.allowed_brands),
    ).fetchall()
    ids = [r["id"] for r in rows]
    audit.log(conn, admin.id, "member.bulk_status", None, {"ids": ids, "to": body.status, "note": body.note})
    return {"updated": len(ids)}


class TagsIn(BaseModel):
    tag_ids: list[int]


@router.put("/{member_id}/tags")
def set_tags(member_id: int, body: TagsIn, admin: Admin = Depends(require("member.edit")),
             conn=Depends(get_conn)):
    m = get_member(conn, admin, member_id)
    valid = [r["id"] for r in conn.execute(
        "SELECT id FROM tags WHERE id = ANY(%s) AND brand_id = %s", (body.tag_ids, m["brand_id"])).fetchall()]
    conn.execute("DELETE FROM member_tags WHERE member_id = %s", (member_id,))
    for t in valid:
        conn.execute("INSERT INTO member_tags (member_id, tag_id) VALUES (%s, %s)", (member_id, t))
    audit.log(conn, admin.id, "member.tags", member_id, {"tag_ids": valid})
    return {"tag_ids": valid}
