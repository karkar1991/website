from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_conn
from ..deps import Admin, brand_scope, require

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    date_to = date_to or date.today()
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to:
        raise HTTPException(400, "date_from must be before date_to")
    if (date_to - date_from).days > 366:
        raise HTTPException(400, "Range too long (max 366 days)")
    return date_from, date_to


@router.get("/summary")
def summary(brand_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
            admin: Admin = Depends(require("finance.view")), conn=Depends(get_conn)):
    d1, d2 = _range(date_from, date_to)
    p = {"brands": brand_scope(admin, brand_id), "d1": d1, "d2": d2 + timedelta(days=1)}
    return conn.execute(
        """
        SELECT b.id AS brand_id, b.name AS brand_name, b.currency,
          (SELECT count(*) FROM members m WHERE m.brand_id = b.id
              AND m.created_at >= %(d1)s AND m.created_at < %(d2)s)                     AS new_members,
          (SELECT count(*) FROM members m WHERE m.brand_id = b.id)                       AS total_members,
          (SELECT COALESCE(sum(amount), 0) FROM wallet_transactions t WHERE t.brand_id = b.id
              AND t.type = 'deposit' AND t.created_at >= %(d1)s AND t.created_at < %(d2)s)   AS deposits,
          (SELECT COALESCE(-sum(amount), 0) FROM wallet_transactions t WHERE t.brand_id = b.id
              AND t.type = 'withdraw' AND t.created_at >= %(d1)s AND t.created_at < %(d2)s)  AS withdrawals,
          (SELECT COALESCE(sum(amount), 0) FROM wallet_transactions t WHERE t.brand_id = b.id
              AND t.type = 'commission' AND t.created_at >= %(d1)s AND t.created_at < %(d2)s) AS commissions,
          (SELECT count(*) FROM deposit_requests r WHERE r.brand_id = b.id AND r.status = 'pending')
                                                                                         AS pending_deposits,
          (SELECT count(*) FROM withdraw_requests r WHERE r.brand_id = b.id AND r.status = 'pending')
                                                                                         AS pending_withdrawals,
          (SELECT COALESCE(sum(balance), 0) FROM wallets w JOIN members m ON m.id = w.member_id
              WHERE m.brand_id = b.id)                                                   AS total_balance
        FROM brands b WHERE b.id = ANY(%(brands)s) ORDER BY b.id
        """,
        p,
    ).fetchall()


@router.get("/daily")
def daily(brand_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
          admin: Admin = Depends(require("finance.view")), conn=Depends(get_conn)):
    d1, d2 = _range(date_from, date_to)
    return conn.execute(
        """
        WITH days AS (
            SELECT d::date AS day FROM generate_series(%(d1)s::date, %(d2)s::date, interval '1 day') d
        ),
        tx AS (
            SELECT brand_id, created_at::date AS day,
                   sum(amount) FILTER (WHERE type = 'deposit')     AS deposits,
                   -sum(amount) FILTER (WHERE type = 'withdraw')   AS withdrawals,
                   sum(amount) FILTER (WHERE type = 'commission')  AS commissions
            FROM wallet_transactions
            WHERE brand_id = ANY(%(brands)s) AND created_at >= %(d1)s AND created_at < %(d2)s::date + 1
            GROUP BY 1, 2
        ),
        mem AS (
            SELECT brand_id, created_at::date AS day, count(*) AS new_members
            FROM members
            WHERE brand_id = ANY(%(brands)s) AND created_at >= %(d1)s AND created_at < %(d2)s::date + 1
            GROUP BY 1, 2
        )
        SELECT d.day, b.id AS brand_id, b.name AS brand_name, b.currency,
               COALESCE(mem.new_members, 0) AS new_members,
               COALESCE(tx.deposits, 0)     AS deposits,
               COALESCE(tx.withdrawals, 0)  AS withdrawals,
               COALESCE(tx.commissions, 0)  AS commissions,
               COALESCE(tx.deposits, 0) - COALESCE(tx.withdrawals, 0) - COALESCE(tx.commissions, 0) AS net
        FROM days d
        CROSS JOIN brands b
        LEFT JOIN tx  ON tx.brand_id = b.id  AND tx.day = d.day
        LEFT JOIN mem ON mem.brand_id = b.id AND mem.day = d.day
        WHERE b.id = ANY(%(brands)s)
        ORDER BY d.day DESC, b.id
        """,
        {"brands": brand_scope(admin, brand_id), "d1": d1, "d2": d2},
    ).fetchall()
