from fastapi import APIRouter, Depends

from ..db import get_conn
from ..deps import Admin, current_admin

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def counts(admin: Admin = Depends(current_admin), conn=Depends(get_conn)):
    """Polled by the admin UI header bell every few seconds."""
    if not admin.can("finance.view"):
        return {"pending_deposits": 0, "pending_withdrawals": 0, "latest": []}
    b = admin.allowed_brands
    dep = conn.execute("SELECT count(*) AS n, max(id) AS last_id FROM deposit_requests"
                       " WHERE status = 'pending' AND brand_id = ANY(%s)", (b,)).fetchone()
    wd = conn.execute("SELECT count(*) AS n, max(id) AS last_id FROM withdraw_requests"
                      " WHERE status = 'pending' AND brand_id = ANY(%s)", (b,)).fetchone()
    latest = conn.execute(
        """(SELECT 'deposit' AS kind, r.id, m.username, r.amount, br.currency, r.created_at
              FROM deposit_requests r JOIN members m ON m.id = r.member_id JOIN brands br ON br.id = r.brand_id
              WHERE r.status = 'pending' AND r.brand_id = ANY(%(b)s) ORDER BY r.id DESC LIMIT 5)
           UNION ALL
           (SELECT 'withdrawal', r.id, m.username, r.amount, br.currency, r.created_at
              FROM withdraw_requests r JOIN members m ON m.id = r.member_id JOIN brands br ON br.id = r.brand_id
              WHERE r.status = 'pending' AND r.brand_id = ANY(%(b)s) ORDER BY r.id DESC LIMIT 5)
           ORDER BY created_at DESC LIMIT 8""",
        {"b": b},
    ).fetchall()
    return {"pending_deposits": dep["n"], "pending_withdrawals": wd["n"],
            "last_deposit_id": dep["last_id"], "last_withdrawal_id": wd["last_id"], "latest": latest}
