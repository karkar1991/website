"""Create FAKE deposits / withdrawals through the real wallet logic.

    docker compose exec api python -m app.seed_demo --deposits 3000 --withdrawals 600
"""
import argparse
import random
from datetime import timedelta
from decimal import Decimal

from . import db
from .config import settings
from .routers.finance import (DepositIn, WithdrawIn, approve_deposit_request, approve_withdraw_request,
                              create_deposit_request, create_withdraw_request)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deposits", type=int, default=3000)
    ap.add_argument("--withdrawals", type=int, default=600)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rnd = random.Random(args.seed)

    db.init_pool(settings.database_url, settings.timezone)
    with db.pool.connection() as conn:
        admin_id = conn.execute("SELECT id FROM admin_users ORDER BY id LIMIT 1").fetchone()["id"]
        channels = {}
        for c in conn.execute("SELECT * FROM payment_channels WHERE is_active").fetchall():
            channels.setdefault(c["brand_id"], []).append(c)
        members = conn.execute(
            "SELECT * FROM members WHERE status = 'normal' AND depth >= 2 ORDER BY random() LIMIT %s",
            (args.deposits,),
        ).fetchall()

        funded = []
        for i, m in enumerate(members):
            ch = rnd.choice(channels[m["brand_id"]])
            amount = Decimal(rnd.choice([10_000, 20_000, 50_000, 100_000, 200_000, 500_000]))
            amount = max(amount, ch["min_amount"])
            req = create_deposit_request(conn, admin_id, m, DepositIn(
                member_id=m["id"], channel_id=ch["id"], amount=amount,
                reference_no=f"DEMO{rnd.randint(10**9, 10**10)}", request_key=f"demo-dep-{m['id']}"))
            if req["status"] == "pending" and rnd.random() < 0.85:  # leave ~15% pending
                approve_deposit_request(conn, admin_id, req, "demo")
                funded.append((m, amount))
            if i % 500 == 0:
                conn.commit()

        for m, bal in funded[: args.withdrawals]:
            amount = (bal * Decimal(rnd.choice(["0.2", "0.5", "0.8"]))).quantize(Decimal("1"))
            req = create_withdraw_request(conn, admin_id, m, WithdrawIn(
                member_id=m["id"], amount=amount, receive_method="kbzpay",
                receive_account="09000000000", receive_name="DEMO USER", request_key=f"demo-wd-{m['id']}"))
            if req["status"] == "pending" and rnd.random() < 0.8:
                approve_withdraw_request(conn, admin_id, req, "demo", f"PAY{rnd.randint(10**6, 10**7)}")

        # spread demo activity over the last 30 days so reports have a shape
        for table in ("deposit_requests", "withdraw_requests"):
            conn.execute(f"UPDATE {table} SET created_at = created_at - random() * interval '30 days'"
                         " WHERE request_key LIKE 'demo-%%'")
        conn.execute("ALTER TABLE wallet_transactions DISABLE TRIGGER trg_ledger_no_update")
        conn.execute("""UPDATE wallet_transactions t SET created_at = r.created_at + interval '10 minutes'
                        FROM deposit_requests r
                        WHERE t.ref_type = 'deposit' AND t.ref_id = r.id::text AND r.request_key LIKE 'demo-%%'""")
        conn.execute("""UPDATE wallet_transactions t SET created_at = r.created_at + interval '1 hour'
                        FROM withdraw_requests r
                        WHERE t.ref_type = 'withdraw' AND t.ref_id = r.id::text AND r.request_key LIKE 'demo-%%'""")
        conn.execute("ALTER TABLE wallet_transactions ENABLE TRIGGER trg_ledger_no_update")

    print(f"Demo data: {len(members)} deposits, {min(len(funded), args.withdrawals)} withdrawals")
    db.close_pool()


if __name__ == "__main__":
    main()
