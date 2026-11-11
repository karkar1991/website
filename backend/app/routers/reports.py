from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_conn
from ..deps import Admin, brand_scope, require

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Test accounts are left out of every report unless include_test=true
REAL = "(%(include_test)s OR {m}.account_type = 'formal')"


def _range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    date_to = date_to or date.today()
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to:
        raise HTTPException(400, "date_from must be before date_to")
    if (date_to - date_from).days > 366:
        raise HTTPException(400, "Range too long (max 366 days)")
    return date_from, date_to


def _params(admin, brand_id, date_from, date_to, include_test):
    d1, d2 = _range(date_from, date_to)
    return {"brands": brand_scope(admin, brand_id), "d1": d1, "d2": d2 + timedelta(days=1),
            "include_test": include_test}


@router.get("/summary")
def summary(brand_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
            include_test: bool = False,
            admin: Admin = Depends(require("finance.view")), conn=Depends(get_conn)):
    p = _params(admin, brand_id, date_from, date_to, include_test)
    tx = """(SELECT COALESCE({sign}sum(t.amount), 0) FROM wallet_transactions t JOIN members tm ON tm.id = t.member_id
             WHERE t.brand_id = b.id AND t.type = '{type}' AND {real}
             AND t.created_at >= %(d1)s AND t.created_at < %(d2)s)"""
    real_tm = REAL.format(m="tm")
    return conn.execute(
        f"""
        SELECT b.id AS brand_id, b.name AS brand_name, b.currency,
          (SELECT count(*) FROM members m WHERE m.brand_id = b.id AND {REAL.format(m="m")}
              AND m.created_at >= %(d1)s AND m.created_at < %(d2)s)                     AS new_members,
          (SELECT count(*) FROM members m WHERE m.brand_id = b.id AND {REAL.format(m="m")}) AS total_members,
          {tx.format(sign="", type="deposit", real=real_tm)}                            AS deposits,
          {tx.format(sign="-", type="withdraw", real=real_tm)}                          AS withdrawals,
          {tx.format(sign="", type="commission", real=real_tm)}                         AS commissions,
          (SELECT count(*) FROM deposit_requests r WHERE r.brand_id = b.id AND r.status = 'pending')
                                                                                         AS pending_deposits,
          (SELECT count(*) FROM withdraw_requests r WHERE r.brand_id = b.id AND r.status = 'pending')
                                                                                         AS pending_withdrawals,
          (SELECT COALESCE(sum(balance), 0) FROM wallets w JOIN members m ON m.id = w.member_id
              WHERE m.brand_id = b.id AND {REAL.format(m="m")})                         AS total_balance
        FROM brands b WHERE b.id = ANY(%(brands)s) ORDER BY b.id
        """,
        p,
    ).fetchall()


@router.get("/daily")
def daily(brand_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
          include_test: bool = False,
          admin: Admin = Depends(require("finance.view")), conn=Depends(get_conn)):
    p = _params(admin, brand_id, date_from, date_to, include_test)
    return conn.execute(
        f"""
        WITH days AS (
            SELECT d::date AS day FROM generate_series(%(d1)s::date, %(d2)s::date - 1, interval '1 day') d
        ),
        tx AS (
            SELECT t.brand_id, t.created_at::date AS day,
                   sum(t.amount) FILTER (WHERE t.type = 'deposit')     AS deposits,
                   -sum(t.amount) FILTER (WHERE t.type = 'withdraw')   AS withdrawals,
                   sum(t.amount) FILTER (WHERE t.type = 'commission')  AS commissions
            FROM wallet_transactions t JOIN members tm ON tm.id = t.member_id
            WHERE t.brand_id = ANY(%(brands)s) AND {REAL.format(m="tm")}
              AND t.created_at >= %(d1)s AND t.created_at < %(d2)s
            GROUP BY 1, 2
        ),
        mem AS (
            SELECT m.brand_id, m.created_at::date AS day, count(*) AS new_members
            FROM members m
            WHERE m.brand_id = ANY(%(brands)s) AND {REAL.format(m="m")}
              AND m.created_at >= %(d1)s AND m.created_at < %(d2)s
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
        p,
    ).fetchall()


@router.get("/sources")
def sources(brand_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
            include_test: bool = False,
            admin: Admin = Depends(require("finance.view")), conn=Depends(get_conn)):
    """Per traffic source: members who registered in the period and what they deposited (in the period)."""
    p = _params(admin, brand_id, date_from, date_to, include_test)
    return conn.execute(
        f"""
        WITH m AS (
            SELECT m.id, m.brand_id, m.source_id FROM members m
            WHERE m.brand_id = ANY(%(brands)s) AND {REAL.format(m="m")}
              AND m.created_at >= %(d1)s AND m.created_at < %(d2)s
        ),
        dep AS (
            SELECT t.member_id, sum(t.amount) AS amount FROM wallet_transactions t
            JOIN m ON m.id = t.member_id
            WHERE t.type = 'deposit' AND t.created_at >= %(d1)s AND t.created_at < %(d2)s
            GROUP BY 1
        )
        SELECT b.name AS brand_name, b.currency, COALESCE(s.name, '(none)') AS source_name, s.code,
               count(*) AS new_members,
               count(dep.member_id) AS depositors,
               round(100.0 * count(dep.member_id) / count(*), 1) AS conversion_pct,
               COALESCE(sum(dep.amount), 0) AS deposits
        FROM m
        JOIN brands b ON b.id = m.brand_id
        LEFT JOIN traffic_sources s ON s.id = m.source_id
        LEFT JOIN dep ON dep.member_id = m.id
        GROUP BY b.id, b.name, b.currency, s.name, s.code
        ORDER BY b.id, new_members DESC
        """,
        p,
    ).fetchall()
