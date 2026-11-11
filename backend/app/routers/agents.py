from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends

from ..db import get_conn
from ..deps import Admin, brand_scope, paging, require

router = APIRouter(prefix="/api/agents", tags=["agents"])

# A member's downline = every member whose path starts with the agent's path.
# The ~>=~ / ~<~ operators let PostgreSQL use the text_pattern_ops index on members.path
# ('~' sorts after every digit and '/', so path || '~' is an upper bound for the subtree).
DOWNLINE = "d.path ~>=~ m.path AND d.path ~<~ (m.path || '~') AND d.id <> m.id"


@router.get("")
def list_agents(
    brand_id: int | None = None,
    username: str | None = None,
    top_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Literal["direct", "new_members", "deposits", "commission"] = "direct",
    page: int = 1,
    size: int = 50,
    admin: Admin = Depends(require("member.view")),
    conn=Depends(get_conn),
):
    """Members who invited at least one person, with team stats for the chosen period."""
    limit, offset = paging(page, size, 200)
    d2 = (date_to or date.today()) + timedelta(days=1)
    d1 = date_from or (d2 - timedelta(days=30))
    p = {"brands": brand_scope(admin, brand_id), "d1": d1, "d2": d2, "limit": limit, "offset": offset}
    w = ["m.brand_id = ANY(%(brands)s)"]
    if username:
        w.append("m.username ILIKE %(u)s")
        p["u"] = f"%{username.strip()}%"
    if top_only:
        w.append("m.depth = 0")
    where = " AND ".join(w)
    base = f"""
        WITH a AS (
            SELECT inviter_id AS id, count(*) AS direct FROM members
            WHERE brand_id = ANY(%(brands)s) AND inviter_id IS NOT NULL GROUP BY inviter_id
        )
        SELECT m.id, m.username, m.brand_id, b.name AS brand_name, b.currency, m.depth, m.status, a.direct
        FROM a JOIN members m ON m.id = a.id JOIN brands b ON b.id = m.brand_id
        WHERE {where}
    """
    total = conn.execute(f"SELECT count(*) AS n FROM ({base}) x", p).fetchone()["n"]

    def with_stats(source_sql: str) -> str:
        return f"""
        SELECT x.*,
          (SELECT count(*) FROM members d WHERE {DOWNLINE})                                    AS downline,
          (SELECT count(*) FROM members d WHERE {DOWNLINE}
              AND d.created_at >= %(d1)s AND d.created_at < %(d2)s)                           AS new_members,
          (SELECT COALESCE(sum(t.amount), 0) FROM members d JOIN wallet_transactions t ON t.member_id = d.id
              WHERE {DOWNLINE} AND t.type = 'deposit'
              AND t.created_at >= %(d1)s AND t.created_at < %(d2)s)                           AS deposits,
          (SELECT COALESCE(sum(t.amount), 0) FROM wallet_transactions t WHERE t.member_id = m.id
              AND t.type = 'commission' AND t.created_at >= %(d1)s AND t.created_at < %(d2)s) AS commission
        FROM ({source_sql}) x JOIN members m ON m.id = x.id
        """

    if sort == "direct":
        # cheap sort first, then stats only for the visible page
        page_sql = f"{base} ORDER BY a.direct DESC, m.id LIMIT %(limit)s OFFSET %(offset)s"
        sql = f"SELECT * FROM ({with_stats(page_sql)}) y ORDER BY direct DESC, id"
    else:
        # Sorting by a period stat needs the stat for every agent. Instead of one subtree query per
        # agent, expand each member into (ancestor, member) pairs once and aggregate.
        sql = f"""
        WITH anc AS (
            SELECT u.a::bigint AS agent_id, s.id AS member_id, s.created_at
            FROM members s,
                 unnest(string_to_array(trim(both '/' from s.path), '/')) AS u(a)
            WHERE s.brand_id = ANY(%(brands)s) AND u.a::bigint <> s.id
        ),
        dl AS (
            SELECT agent_id, count(*) AS downline,
                   count(*) FILTER (WHERE created_at >= %(d1)s AND created_at < %(d2)s) AS new_members
            FROM anc GROUP BY agent_id
        ),
        dep AS (
            SELECT anc.agent_id, sum(t.amount) AS deposits
            FROM wallet_transactions t JOIN anc ON anc.member_id = t.member_id
            WHERE t.type = 'deposit' AND t.brand_id = ANY(%(brands)s)
              AND t.created_at >= %(d1)s AND t.created_at < %(d2)s
            GROUP BY anc.agent_id
        ),
        com AS (
            SELECT member_id AS agent_id, sum(amount) AS commission FROM wallet_transactions
            WHERE type = 'commission' AND brand_id = ANY(%(brands)s)
              AND created_at >= %(d1)s AND created_at < %(d2)s
            GROUP BY member_id
        )
        SELECT x.*, COALESCE(dl.downline, 0) AS downline, COALESCE(dl.new_members, 0) AS new_members,
               COALESCE(dep.deposits, 0) AS deposits, COALESCE(com.commission, 0) AS commission
        FROM ({base}) x
        LEFT JOIN dl  ON dl.agent_id = x.id
        LEFT JOIN dep ON dep.agent_id = x.id
        LEFT JOIN com ON com.agent_id = x.id
        ORDER BY {sort} DESC, x.id
        LIMIT %(limit)s OFFSET %(offset)s
        """
    rows = conn.execute(sql, p).fetchall()
    return {"total": total, "rows": rows, "date_from": d1, "date_to": d2 - timedelta(days=1)}
