import csv
import io
import re
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from pydantic import BaseModel, Field

from .. import audit
from ..config import settings
from ..db import get_conn
from ..deps import Admin, brand_scope, paging, require

router = APIRouter(prefix="/api/members", tags=["members"])

Status = Literal["normal", "blacklist", "leaving", "left"]
AccountType = Literal["formal", "test"]
USERNAME_RE = r"^[A-Za-z0-9_.]+$"

SELECT_MEMBER = """
SELECT m.id, m.brand_id, b.name AS brand_name, m.username, m.full_name, m.phone,
       m.status, m.account_type, m.depth, m.path,
       m.vip_level_id, v.level AS vip_level, v.name AS vip_name,
       m.member_level_id, ml.name AS member_level,
       m.source_id, s.name AS source_name,
       inv.id AS inviter_id, inv.username AS inviter_username,
       top.id AS top_agent_id, top.username AS top_agent_username,
       b.currency, COALESCE(w.balance, 0) AS balance, COALESCE(w.frozen, 0) AS frozen,
       m.created_at
FROM members m
JOIN brands b              ON b.id = m.brand_id
LEFT JOIN vip_levels v     ON v.id = m.vip_level_id
LEFT JOIN member_levels ml ON ml.id = m.member_level_id
LEFT JOIN traffic_sources s ON s.id = m.source_id
LEFT JOIN members inv      ON inv.id = m.inviter_id
LEFT JOIN members top      ON m.depth > 0 AND top.id = split_part(m.path, '/', 2)::bigint
LEFT JOIN wallets w        ON w.member_id = m.id
"""


class MemberFilter:
    def __init__(
        self,
        brand_id: int | None = None,
        username: str | None = None,
        username_like: str | None = None,
        phone: str | None = None,
        status: Status | None = None,
        account_type: AccountType | None = None,
        vip_level: int | None = None,
        member_level_id: int | None = None,
        source_id: int | None = None,
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
        simple = {"status": "m.status", "account_type": "m.account_type",
                  "member_level_id": "m.member_level_id", "source_id": "m.source_id"}
        for key, col in simple.items():
            if getattr(self, key) is not None:
                w.append(f"{col} = %({key})s")
                p[key] = getattr(self, key)
        if self.username:
            w.append("m.username = %(username)s")
            p["username"] = self.username.strip()
        if self.username_like:
            w.append("m.username ILIKE %(ulike)s")
            p["ulike"] = f"%{self.username_like.strip()}%"
        if self.phone:
            w.append("m.phone LIKE %(phone)s")
            p["phone"] = f"%{self.phone.strip()}%"
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


def _check_refs(conn, brand_id: int, vip_level_id=None, member_level_id=None, source_id=None):
    """Make sure the referenced level / source rows belong to the same brand."""
    for table, value in (("vip_levels", vip_level_id), ("member_levels", member_level_id),
                         ("traffic_sources", source_id)):
        if value is not None and conn.execute(
                f"SELECT 1 FROM {table} WHERE id = %s AND brand_id = %s", (value, brand_id)).fetchone() is None:
            raise HTTPException(400, f"{table} {value} does not belong to this brand")


def _insert_member(conn, brand_id: int, username: str, inviter: dict | None, **fields) -> int:
    row = conn.execute(
        """INSERT INTO members (brand_id, username, full_name, phone, account_type, vip_level_id,
                                member_level_id, source_id, inviter_id, depth)
           VALUES (%(brand_id)s, %(username)s, %(full_name)s, %(phone)s, %(account_type)s, %(vip_level_id)s,
                   %(member_level_id)s, %(source_id)s, %(inviter_id)s, %(depth)s) RETURNING id""",
        {"brand_id": brand_id, "username": username, "inviter_id": inviter["id"] if inviter else None,
         "depth": inviter["depth"] + 1 if inviter else 0, **fields},
    ).fetchone()
    path = (inviter["path"] if inviter else "/") + f"{row['id']}/"
    conn.execute("UPDATE members SET path = %s WHERE id = %s", (path, row["id"]))
    conn.execute("INSERT INTO wallets (member_id) VALUES (%s)", (row["id"],))
    return row["id"]


def _lowest(conn, table: str, brand_id: int) -> int | None:
    order = "level" if table == "vip_levels" else "sort"
    r = conn.execute(f"SELECT id FROM {table} WHERE brand_id = %s ORDER BY {order} LIMIT 1", (brand_id,)).fetchone()
    return r["id"] if r else None


# ------------------------------------------------------------------ list / export
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
    cols = ["id", "brand_name", "username", "full_name", "phone", "status", "account_type", "vip_name",
            "member_level", "source_name", "inviter_username", "top_agent_username", "currency", "balance",
            "frozen", "created_at"]
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


# ------------------------------------------------------------------ create / import
class MemberCreate(BaseModel):
    brand_id: int
    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_RE)
    full_name: str | None = None
    phone: str | None = None
    inviter_username: str | None = None
    account_type: AccountType = "formal"
    vip_level_id: int | None = None
    member_level_id: int | None = None
    source_id: int | None = None


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
    _check_refs(conn, body.brand_id, body.vip_level_id, body.member_level_id, body.source_id)
    member_id = _insert_member(
        conn, body.brand_id, body.username, inviter,
        full_name=body.full_name, phone=body.phone, account_type=body.account_type,
        vip_level_id=body.vip_level_id or _lowest(conn, "vip_levels", body.brand_id),
        member_level_id=body.member_level_id or _lowest(conn, "member_levels", body.brand_id),
        source_id=body.source_id,
    )
    audit.log(conn, admin.id, "member.create", member_id, body.model_dump())
    return conn.execute(f"{SELECT_MEMBER} WHERE m.id = %s", (member_id,)).fetchone()


IMPORT_COLUMNS = ["username", "full_name", "phone", "inviter_username", "account_type", "vip_level",
                  "member_level", "source_code"]


@router.get("/import-template")
def import_template(admin: Admin = Depends(require("member.edit"))):
    wb = Workbook()
    ws = wb.active
    ws.title = "members"
    ws.append(IMPORT_COLUMNS)
    ws.append(["new_agent01", "Aung Aung", "09123456789", "", "formal", 0, "Free", "telesale"])
    ws.append(["new_user01", "Su Su", "09987654321", "new_agent01", "formal", 0, "Free", "referral"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="member_import_template.xlsx"'})


def _read_rows(file: UploadFile) -> list[dict]:
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10 MB)")
    name = (file.filename or "").lower()
    if name.endswith(".csv"):
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig")))
        table = list(reader)
    elif name.endswith(".xlsx"):
        ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
        table = [list(r) for r in ws.iter_rows(values_only=True)]
    else:
        raise HTTPException(400, "Upload an .xlsx or .csv file")
    if not table:
        raise HTTPException(400, "File is empty")
    header = [str(h or "").strip().lower() for h in table[0]]
    if "username" not in header:
        raise HTTPException(400, f"Header row must contain: {', '.join(IMPORT_COLUMNS)}")
    rows = []
    for r in table[1:]:
        item = {h: ("" if v is None else str(v).strip()) for h, v in zip(header, r) if h in IMPORT_COLUMNS}
        if any(item.values()):
            rows.append(item)
    if len(rows) > 20000:
        raise HTTPException(400, "Max 20,000 rows per import")
    return rows


@router.post("/import")
def import_members(
    brand_id: int = Form(...),
    dry_run: bool = Form(True),
    file: UploadFile = File(...),
    admin: Admin = Depends(require("member.edit")),
    conn=Depends(get_conn),
):
    """Validate every row first. Nothing is written unless all rows are valid and dry_run is false.
    Inviters may be existing members or rows earlier in the same file."""
    brand_scope(admin, brand_id)
    rows = _read_rows(file)
    vip = {str(r["level"]): r["id"] for r in conn.execute(
        "SELECT id, level FROM vip_levels WHERE brand_id = %s", (brand_id,)).fetchall()}
    levels = {r["name"].lower(): r["id"] for r in conn.execute(
        "SELECT id, name FROM member_levels WHERE brand_id = %s", (brand_id,)).fetchall()}
    sources = {r["code"].lower(): r["id"] for r in conn.execute(
        "SELECT id, code FROM traffic_sources WHERE brand_id = %s", (brand_id,)).fetchall()}
    names = [r.get("username", "") for r in rows]
    existing = {r["username"]: r for r in conn.execute(
        "SELECT id, username, path, depth FROM members WHERE brand_id = %s AND username = ANY(%s)",
        (brand_id, names + [r.get("inviter_username", "") for r in rows])).fetchall()}

    errors, seen, clean = [], set(), []
    for i, r in enumerate(rows, start=2):  # row 1 = header
        u = r.get("username", "")
        problems = []
        if not re.fullmatch(USERNAME_RE, u) or not 3 <= len(u) <= 50:
            problems.append("invalid username")
        if u in seen:
            problems.append("duplicate username in file")
        if u in existing:
            problems.append("username already exists")
        inv = r.get("inviter_username", "")
        if inv and inv not in existing and inv not in seen:
            problems.append(f"inviter '{inv}' not found (must exist or be on an earlier row)")
        at = (r.get("account_type") or "formal").lower()
        if at not in ("formal", "test"):
            problems.append("account_type must be formal or test")
        v = r.get("vip_level", "")
        if v.endswith(".0"):
            v = v[:-2]
        if v and v not in vip:
            problems.append(f"unknown vip_level '{v}'")
        lv = r.get("member_level", "").lower()
        if lv and lv not in levels:
            problems.append(f"unknown member_level '{r.get('member_level')}'")
        sc = r.get("source_code", "").lower()
        if sc and sc not in sources:
            problems.append(f"unknown source_code '{r.get('source_code')}'")
        if problems:
            errors.append({"row": i, "username": u, "errors": problems})
        seen.add(u)
        clean.append({"username": u, "full_name": r.get("full_name") or None, "phone": r.get("phone") or None,
                      "inviter": inv or None, "account_type": at,
                      "vip_level_id": vip.get(v) if v else _lowest(conn, "vip_levels", brand_id),
                      "member_level_id": levels.get(lv) if lv else _lowest(conn, "member_levels", brand_id),
                      "source_id": sources.get(sc)})

    result = {"total_rows": len(rows), "valid_rows": len(rows) - len(errors), "errors": errors[:500],
              "error_count": len(errors), "imported": 0}
    if dry_run or errors or not rows:
        return result

    created = {}
    for c in clean:
        inviter = existing.get(c["inviter"]) or created.get(c["inviter"]) if c["inviter"] else None
        mid = _insert_member(conn, brand_id, c["username"], inviter, full_name=c["full_name"], phone=c["phone"],
                             account_type=c["account_type"], vip_level_id=c["vip_level_id"],
                             member_level_id=c["member_level_id"], source_id=c["source_id"])
        created[c["username"]] = conn.execute("SELECT id, path, depth FROM members WHERE id = %s",
                                              (mid,)).fetchone()
    result["imported"] = len(created)
    audit.log(conn, admin.id, "member.import", None,
              {"brand_id": brand_id, "rows": len(created), "file": file.filename})
    return result


# ------------------------------------------------------------------ detail / tree
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
def member_children(member_id: int, page: int = 1, size: int = 100,
                    admin: Admin = Depends(require("member.view")), conn=Depends(get_conn)):
    get_member(conn, admin, member_id)
    limit, offset = paging(page, size)
    rows = conn.execute(
        """SELECT m.id, m.username, m.status, m.depth,
                  (SELECT count(*) FROM members c WHERE c.inviter_id = m.id) AS children
           FROM members m WHERE m.inviter_id = %s ORDER BY m.id LIMIT %s OFFSET %s""",
        (member_id, limit + 1, offset),
    ).fetchall()
    return {"rows": rows[:limit], "has_more": len(rows) > limit}


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


# ------------------------------------------------------------------ edit
class MemberPatch(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    account_type: AccountType | None = None
    vip_level_id: int | None = None
    member_level_id: int | None = None
    source_id: int | None = None


@router.patch("/{member_id}")
def update_member(member_id: int, body: MemberPatch, admin: Admin = Depends(require("member.edit")),
                  conn=Depends(get_conn)):
    m = get_member(conn, admin, member_id, lock=True)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return {"id": member_id, "updated": []}
    _check_refs(conn, m["brand_id"], changes.get("vip_level_id"), changes.get("member_level_id"),
                changes.get("source_id"))
    sets = ", ".join(f"{k} = %({k})s" for k in changes)  # keys come from the pydantic model only
    conn.execute(f"UPDATE members SET {sets}, updated_at = now() WHERE id = %(id)s", {**changes, "id": member_id})
    audit.log(conn, admin.id, "member.update", member_id,
              {k: {"from": m[k], "to": v} for k, v in changes.items()})
    return {"id": member_id, "updated": list(changes)}


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
