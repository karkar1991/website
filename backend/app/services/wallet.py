"""All money movement goes through this module.

Rules:
  * every change locks the wallet row first (SELECT ... FOR UPDATE)
  * every balance change writes exactly one ledger row (wallet_transactions)
  * ledger rows are unique per (ref_type, ref_id, type, member_id) -> no double posting
  * balance can never drop below frozen (also enforced by a DB CHECK)
"""
from decimal import ROUND_HALF_UP, Decimal


class WalletError(Exception):
    pass


CENT = Decimal("0.01")


def _lock(conn, member_id: int) -> dict:
    conn.execute("INSERT INTO wallets (member_id) VALUES (%s) ON CONFLICT DO NOTHING", (member_id,))
    return conn.execute(
        """SELECT w.member_id, w.balance, w.frozen, m.brand_id
           FROM wallets w JOIN members m ON m.id = w.member_id
           WHERE w.member_id = %s FOR UPDATE OF w""",
        (member_id,),
    ).fetchone()


def _ledger(conn, w, txn_type, amount, balance_after, ref_type, ref_id, admin_id, note):
    row = conn.execute(
        """INSERT INTO wallet_transactions
               (member_id, brand_id, type, amount, balance_after, ref_type, ref_id, admin_id, note)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (ref_type, ref_id, type, member_id) DO NOTHING
           RETURNING id""",
        (w["member_id"], w["brand_id"], txn_type, amount, balance_after, ref_type, str(ref_id), admin_id, note),
    ).fetchone()
    if row is None:
        raise WalletError("This transaction was already posted")
    return row["id"]


def credit(conn, member_id: int, amount: Decimal, txn_type: str, ref_type: str, ref_id,
           admin_id: int | None = None, note: str | None = None) -> Decimal:
    """Add (amount > 0) or remove (amount < 0) money. Returns the new balance."""
    amount = Decimal(amount).quantize(CENT)
    if amount == 0:
        raise WalletError("Amount must not be zero")
    w = _lock(conn, member_id)
    new_balance = w["balance"] + amount
    if new_balance < w["frozen"]:
        raise WalletError("Insufficient available balance")
    _ledger(conn, w, txn_type, amount, new_balance, ref_type, ref_id, admin_id, note)
    conn.execute(
        "UPDATE wallets SET balance = %s, updated_at = now() WHERE member_id = %s",
        (new_balance, member_id),
    )
    return new_balance


def freeze(conn, member_id: int, amount: Decimal) -> None:
    w = _lock(conn, member_id)
    if w["balance"] - w["frozen"] < amount:
        raise WalletError("Insufficient available balance")
    conn.execute(
        "UPDATE wallets SET frozen = frozen + %s, updated_at = now() WHERE member_id = %s",
        (amount, member_id),
    )


def unfreeze(conn, member_id: int, amount: Decimal) -> None:
    w = _lock(conn, member_id)
    if w["frozen"] < amount:
        raise WalletError("Frozen amount mismatch")
    conn.execute(
        "UPDATE wallets SET frozen = frozen - %s, updated_at = now() WHERE member_id = %s",
        (amount, member_id),
    )


def settle_withdraw(conn, member_id: int, amount: Decimal, ref_id, admin_id: int | None,
                    note: str | None = None) -> Decimal:
    """Pay out a frozen amount: balance and frozen both go down."""
    w = _lock(conn, member_id)
    if w["frozen"] < amount:
        raise WalletError("Frozen amount mismatch")
    new_balance = w["balance"] - amount
    _ledger(conn, w, "withdraw", -amount, new_balance, "withdraw", ref_id, admin_id, note)
    conn.execute(
        "UPDATE wallets SET balance = %s, frozen = frozen - %s, updated_at = now() WHERE member_id = %s",
        (new_balance, amount, member_id),
    )
    return new_balance


def pay_commissions(conn, member: dict, amount: Decimal, deposit_id: int, admin_id: int | None) -> list[dict]:
    """Pay inviters up the referral tree according to commission_rules."""
    ancestors = [int(x) for x in member["path"].strip("/").split("/")[:-1]][::-1]  # nearest first
    if not ancestors:
        return []
    rules = conn.execute(
        "SELECT depth_up, percent FROM commission_rules WHERE brand_id = %s ORDER BY depth_up",
        (member["brand_id"],),
    ).fetchall()
    paid = []
    for rule in rules:
        if rule["depth_up"] > len(ancestors):
            break
        agent_id = ancestors[rule["depth_up"] - 1]
        status = conn.execute("SELECT status FROM members WHERE id = %s", (agent_id,)).fetchone()
        if status is None or status["status"] != "normal":
            continue  # blacklisted / leaving agents earn nothing
        value = (amount * rule["percent"] / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        if value <= 0:
            continue
        credit(conn, agent_id, value, "commission", "deposit", deposit_id, admin_id,
               f"L{rule['depth_up']} commission from member {member['id']}")
        paid.append({"member_id": agent_id, "level": rule["depth_up"], "amount": value})
    return paid
