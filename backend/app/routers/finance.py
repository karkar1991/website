import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import audit
from ..db import get_conn
from ..deps import Admin, brand_scope, paging, require
from ..services import wallet
from ..services.wallet import WalletError
from .members import get_member

router = APIRouter(prefix="/api/finance", tags=["finance"])

Money = Decimal
ReqStatus = Literal["pending", "approved", "rejected"]


def _wallet_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except WalletError as e:
        raise HTTPException(400, str(e))


def _date_filters(w: list, p: dict, col: str, date_from: date | None, date_to: date | None):
    if date_from:
        w.append(f"{col} >= %(dfrom)s")
        p["dfrom"] = date_from
    if date_to:
        w.append(f"{col} < %(dto)s")
        p["dto"] = date_to + timedelta(days=1)


# ------------------------------------------------------------------ channels
class ChannelIn(BaseModel):
    brand_id: int
    name: str
    type: Literal["kbzpay", "wavepay", "bank", "promptpay", "other"]
    account_name: str
    account_no: str
    min_amount: Money = Field(default=Decimal(0), ge=0)
    max_amount: Money = Field(default=Decimal(10_000_000), gt=0)
    is_active: bool = True


class ChannelPatch(BaseModel):
    name: str | None = None
    account_name: str | None = None
    account_no: str | None = None
    min_amount: Money | None = Field(default=None, ge=0)
    max_amount: Money | None = Field(default=None, gt=0)
    is_active: bool | None = None


@router.get("/channels")
def list_channels(brand_id: int | None = None, admin: Admin = Depends(require("finance.view")),
                  conn=Depends(get_conn)):
    return conn.execute(
        """SELECT c.*, b.name AS brand_name FROM payment_channels c JOIN brands b ON b.id = c.brand_id
           WHERE c.brand_id = ANY(%s) ORDER BY c.brand_id, c.id""",
        (brand_scope(admin, brand_id),),
    ).fetchall()


@router.post("/channels", status_code=201)
def create_channel(body: ChannelIn, admin: Admin = Depends(require("channel.manage")), conn=Depends(get_conn)):
    brand_scope(admin, body.brand_id)
    row = conn.execute(
        """INSERT INTO payment_channels (brand_id, name, type, account_name, account_no,
                                         min_amount, max_amount, is_active)
           VALUES (%(brand_id)s, %(name)s, %(type)s, %(account_name)s, %(account_no)s,
                   %(min_amount)s, %(max_amount)s, %(is_active)s) RETURNING *""",
        body.model_dump(),
    ).fetchone()
    audit.log(conn, admin.id, "channel.create", row["id"], body.model_dump(mode="json"))
    return row


@router.patch("/channels/{channel_id}")
def update_channel(channel_id: int, body: ChannelPatch, admin: Admin = Depends(require("channel.manage")),
                   conn=Depends(get_conn)):
    ch = conn.execute("SELECT * FROM payment_channels WHERE id = %s AND brand_id = ANY(%s)",
                      (channel_id, admin.allowed_brands)).fetchone()
    if ch is None:
        raise HTTPException(404, "Channel not found")
    changes = body.model_dump(exclude_none=True)
    if not changes:
        return ch
    sets = ", ".join(f"{k} = %({k})s" for k in changes)  # keys come from the pydantic model only
    row = conn.execute(f"UPDATE payment_channels SET {sets} WHERE id = %(id)s RETURNING *",
                       {**changes, "id": channel_id}).fetchone()
    audit.log(conn, admin.id, "channel.update", channel_id, body.model_dump(mode="json", exclude_none=True))
    return row


# ------------------------------------------------------------------ deposits
class DepositIn(BaseModel):
    member_id: int
    channel_id: int
    amount: Money = Field(gt=0, max_digits=18, decimal_places=2)
    reference_no: str | None = None
    proof_url: str | None = None
    note: str | None = None
    request_key: str | None = Field(default=None, max_length=100)


class ReviewIn(BaseModel):
    note: str | None = None
    payout_ref: str | None = None  # withdrawals only: transfer ID after paying


def _list_requests(table: str, conn, admin: Admin, brand_id, status, username, date_from, date_to, page, size):
    limit, offset = paging(page, size)
    p: dict = {"brands": brand_scope(admin, brand_id)}
    w = ["r.brand_id = ANY(%(brands)s)"]
    if status:
        w.append("r.status = %(status)s")
        p["status"] = status
    if username:
        w.append("m.username = %(username)s")
        p["username"] = username.strip()
    _date_filters(w, p, "r.created_at", date_from, date_to)
    where = " AND ".join(w)
    extra = "c.name AS channel_name," if table == "deposit_requests" else ""
    join = "LEFT JOIN payment_channels c ON c.id = r.channel_id" if table == "deposit_requests" else ""
    base = f"FROM {table} r JOIN members m ON m.id = r.member_id JOIN brands b ON b.id = r.brand_id {join}"
    total = conn.execute(f"SELECT count(*) AS n, COALESCE(sum(r.amount), 0) AS amount {base} WHERE {where}",
                         p).fetchone()
    rows = conn.execute(
        f"""SELECT r.*, {extra} m.username, b.name AS brand_name, b.currency,
                   cb.username AS created_by_name, rb.username AS reviewed_by_name
            {base}
            LEFT JOIN admin_users cb ON cb.id = r.created_by
            LEFT JOIN admin_users rb ON rb.id = r.reviewed_by
            WHERE {where} ORDER BY r.id DESC LIMIT %(limit)s OFFSET %(offset)s""",
        {**p, "limit": limit, "offset": offset},
    ).fetchall()
    return {"total": total["n"], "total_amount": total["amount"], "rows": rows}


def _lock_request(conn, table: str, req_id: int, admin: Admin) -> dict:
    r = conn.execute(f"SELECT * FROM {table} WHERE id = %s AND brand_id = ANY(%s) FOR UPDATE",
                     (req_id, admin.allowed_brands)).fetchone()
    if r is None:
        raise HTTPException(404, "Request not found")
    if r["status"] != "pending":
        raise HTTPException(409, f"Request already {r['status']}")
    return r


@router.get("/deposits")
def list_deposits(brand_id: int | None = None, status: ReqStatus | None = None, username: str | None = None,
                  date_from: date | None = None, date_to: date | None = None, page: int = 1, size: int = 50,
                  admin: Admin = Depends(require("finance.view")), conn=Depends(get_conn)):
    return _list_requests("deposit_requests", conn, admin, brand_id, status, username, date_from, date_to,
                          page, size)


def create_deposit_request(conn, admin_id: int | None, member: dict, body: DepositIn) -> dict:
    ch = conn.execute("SELECT * FROM payment_channels WHERE id = %s", (body.channel_id,)).fetchone()
    if ch is None or ch["brand_id"] != member["brand_id"]:
        raise HTTPException(400, "Channel does not belong to the member's brand")
    if not ch["is_active"]:
        raise HTTPException(400, "Channel is disabled")
    if not (ch["min_amount"] <= body.amount <= ch["max_amount"]):
        raise HTTPException(400, f"Amount must be between {ch['min_amount']} and {ch['max_amount']}")
    key = body.request_key or str(uuid.uuid4())
    row = conn.execute(
        """INSERT INTO deposit_requests (member_id, brand_id, channel_id, amount, reference_no, proof_url,
                                         note, request_key, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (request_key) DO NOTHING RETURNING *""",
        (member["id"], member["brand_id"], ch["id"], body.amount, body.reference_no, body.proof_url,
         body.note, key, admin_id),
    ).fetchone()
    if row is None:  # same request_key sent twice -> return the original
        row = conn.execute("SELECT * FROM deposit_requests WHERE request_key = %s", (key,)).fetchone()
    return row


@router.post("/deposits", status_code=201)
def create_deposit(body: DepositIn, admin: Admin = Depends(require("finance.create")), conn=Depends(get_conn)):
    member = get_member(conn, admin, body.member_id)
    row = create_deposit_request(conn, admin.id, member, body)
    audit.log(conn, admin.id, "deposit.create", row["id"], body.model_dump(mode="json"))
    return row


def approve_deposit_request(conn, admin_id: int | None, r: dict, note: str | None) -> dict:
    member = conn.execute("SELECT * FROM members WHERE id = %s", (r["member_id"],)).fetchone()
    balance = _wallet_call(wallet.credit, conn, r["member_id"], r["amount"], "deposit", "deposit", r["id"],
                           admin_id, note)
    commissions = _wallet_call(wallet.pay_commissions, conn, member, r["amount"], r["id"], admin_id)
    conn.execute(
        """UPDATE deposit_requests SET status = 'approved', reviewed_by = %s, reviewed_at = now(),
               note = COALESCE(%s, note) WHERE id = %s""",
        (admin_id, note, r["id"]),
    )
    return {"id": r["id"], "status": "approved", "balance": balance, "commissions": commissions}


@router.post("/deposits/{req_id}/approve")
def approve_deposit(req_id: int, body: ReviewIn, admin: Admin = Depends(require("finance.approve")),
                    conn=Depends(get_conn)):
    r = _lock_request(conn, "deposit_requests", req_id, admin)
    result = approve_deposit_request(conn, admin.id, r, body.note)
    audit.log(conn, admin.id, "deposit.approve", req_id,
              {"amount": str(r["amount"]), "commissions": len(result["commissions"])})
    return result


@router.post("/deposits/{req_id}/reject")
def reject_deposit(req_id: int, body: ReviewIn, admin: Admin = Depends(require("finance.approve")),
                   conn=Depends(get_conn)):
    _lock_request(conn, "deposit_requests", req_id, admin)
    conn.execute(
        """UPDATE deposit_requests SET status = 'rejected', reviewed_by = %s, reviewed_at = now(),
               note = COALESCE(%s, note) WHERE id = %s""",
        (admin.id, body.note, req_id),
    )
    audit.log(conn, admin.id, "deposit.reject", req_id, {"note": body.note})
    return {"id": req_id, "status": "rejected"}


# ------------------------------------------------------------------ withdrawals
class WithdrawIn(BaseModel):
    member_id: int
    amount: Money = Field(gt=0, max_digits=18, decimal_places=2)
    receive_method: Literal["kbzpay", "wavepay", "bank", "promptpay", "other"]
    receive_account: str
    receive_name: str
    note: str | None = None
    request_key: str | None = Field(default=None, max_length=100)


@router.get("/withdrawals")
def list_withdrawals(brand_id: int | None = None, status: ReqStatus | None = None, username: str | None = None,
                     date_from: date | None = None, date_to: date | None = None, page: int = 1, size: int = 50,
                     admin: Admin = Depends(require("finance.view")), conn=Depends(get_conn)):
    return _list_requests("withdraw_requests", conn, admin, brand_id, status, username, date_from, date_to,
                          page, size)


def create_withdraw_request(conn, admin_id: int | None, member: dict, body: WithdrawIn) -> dict:
    key = body.request_key or str(uuid.uuid4())
    existing = conn.execute("SELECT * FROM withdraw_requests WHERE request_key = %s", (key,)).fetchone()
    if existing:
        return existing
    if member["status"] != "normal":
        raise HTTPException(400, f"Member status is {member['status']}; withdrawals are blocked")
    _wallet_call(wallet.freeze, conn, member["id"], body.amount)
    return conn.execute(
        """INSERT INTO withdraw_requests (member_id, brand_id, amount, receive_method, receive_account,
                                          receive_name, note, request_key, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
        (member["id"], member["brand_id"], body.amount, body.receive_method, body.receive_account,
         body.receive_name, body.note, key, admin_id),
    ).fetchone()


@router.post("/withdrawals", status_code=201)
def create_withdraw(body: WithdrawIn, admin: Admin = Depends(require("finance.create")), conn=Depends(get_conn)):
    member = get_member(conn, admin, body.member_id)
    row = create_withdraw_request(conn, admin.id, member, body)
    audit.log(conn, admin.id, "withdraw.create", row["id"], body.model_dump(mode="json"))
    return row


def approve_withdraw_request(conn, admin_id: int | None, r: dict, note: str | None,
                             payout_ref: str | None) -> dict:
    balance = _wallet_call(wallet.settle_withdraw, conn, r["member_id"], r["amount"], r["id"], admin_id, note)
    conn.execute(
        """UPDATE withdraw_requests SET status = 'approved', reviewed_by = %s, reviewed_at = now(),
               payout_ref = %s, note = COALESCE(%s, note) WHERE id = %s""",
        (admin_id, payout_ref, note, r["id"]),
    )
    return {"id": r["id"], "status": "approved", "balance": balance}


@router.post("/withdrawals/{req_id}/approve")
def approve_withdraw(req_id: int, body: ReviewIn, admin: Admin = Depends(require("finance.approve")),
                     conn=Depends(get_conn)):
    r = _lock_request(conn, "withdraw_requests", req_id, admin)
    result = approve_withdraw_request(conn, admin.id, r, body.note, body.payout_ref)
    audit.log(conn, admin.id, "withdraw.approve", req_id,
              {"amount": str(r["amount"]), "payout_ref": body.payout_ref})
    return result


@router.post("/withdrawals/{req_id}/reject")
def reject_withdraw(req_id: int, body: ReviewIn, admin: Admin = Depends(require("finance.approve")),
                    conn=Depends(get_conn)):
    r = _lock_request(conn, "withdraw_requests", req_id, admin)
    _wallet_call(wallet.unfreeze, conn, r["member_id"], r["amount"])
    conn.execute(
        """UPDATE withdraw_requests SET status = 'rejected', reviewed_by = %s, reviewed_at = now(),
               note = COALESCE(%s, note) WHERE id = %s""",
        (admin.id, body.note, req_id),
    )
    audit.log(conn, admin.id, "withdraw.reject", req_id, {"note": body.note})
    return {"id": req_id, "status": "rejected"}


# ------------------------------------------------------------------ manual adjust + ledger
class AdjustIn(BaseModel):
    member_id: int
    amount: Money = Field(max_digits=18, decimal_places=2)  # + add, - remove
    note: str = Field(min_length=3)


@router.post("/adjust")
def adjust(body: AdjustIn, admin: Admin = Depends(require("finance.approve")), conn=Depends(get_conn)):
    get_member(conn, admin, body.member_id)
    ref = str(uuid.uuid4())
    balance = _wallet_call(wallet.credit, conn, body.member_id, body.amount, "adjust", "adjust", ref,
                           admin.id, body.note)
    audit.log(conn, admin.id, "wallet.adjust", body.member_id, {"amount": str(body.amount), "note": body.note})
    return {"member_id": body.member_id, "balance": balance}


@router.get("/transactions")
def transactions(brand_id: int | None = None, member_id: int | None = None, username: str | None = None,
                 type: Literal["deposit", "withdraw", "commission", "adjust"] | None = None,
                 date_from: date | None = None, date_to: date | None = None, page: int = 1, size: int = 50,
                 admin: Admin = Depends(require("finance.view")), conn=Depends(get_conn)):
    limit, offset = paging(page, size)
    p: dict = {"brands": brand_scope(admin, brand_id)}
    w = ["t.brand_id = ANY(%(brands)s)"]
    if member_id:
        w.append("t.member_id = %(mid)s")
        p["mid"] = member_id
    if username:
        w.append("m.username = %(username)s")
        p["username"] = username.strip()
    if type:
        w.append("t.type = %(type)s")
        p["type"] = type
    _date_filters(w, p, "t.created_at", date_from, date_to)
    where = " AND ".join(w)
    base = "FROM wallet_transactions t JOIN members m ON m.id = t.member_id"
    total = conn.execute(f"SELECT count(*) AS n {base} WHERE {where}", p).fetchone()["n"]
    rows = conn.execute(
        f"""SELECT t.*, m.username, a.username AS admin_name {base}
            LEFT JOIN admin_users a ON a.id = t.admin_id
            WHERE {where} ORDER BY t.id DESC LIMIT %(limit)s OFFSET %(offset)s""",
        {**p, "limit": limit, "offset": offset},
    ).fetchall()
    return {"total": total, "rows": rows}
