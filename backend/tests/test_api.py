import uuid
from decimal import Decimal


def D(x):
    return Decimal(str(x))


def new_member(client, auth, inviter=None, brand_id=1):
    name = "t_" + uuid.uuid4().hex[:10]
    r = client.post("/api/members", headers=auth,
                    json={"brand_id": brand_id, "username": name, "inviter_username": inviter})
    assert r.status_code == 201, r.text
    return r.json()


def channel_id(client, auth, brand_id=1, type_="kbzpay"):
    chans = client.get("/api/finance/channels", headers=auth, params={"brand_id": brand_id}).json()
    return next(c["id"] for c in chans if c["type"] == type_)


def balance(client, auth, member_id):
    m = client.get(f"/api/members/{member_id}", headers=auth).json()
    return D(m["balance"]), D(m["frozen"])


# ---------------------------------------------------------------- auth
def test_login_rejects_bad_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_requires_token(client):
    assert client.get("/api/members").status_code == 401


def test_refresh(client):
    import os
    t = client.post("/api/auth/login", json={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]}).json()
    r = client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert r.status_code == 200 and "access_token" in r.json()
    # an access token must not work as a refresh token
    assert client.post("/api/auth/refresh", json={"refresh_token": t["access_token"]}).status_code == 401


# ---------------------------------------------------------------- members
def test_member_list_and_filters(client, auth):
    r = client.get("/api/members", headers=auth, params={"size": 10})
    body = r.json()
    assert r.status_code == 200 and body["total"] >= 100000 and len(body["rows"]) == 10
    r = client.get("/api/members", headers=auth, params={"brand_id": 1, "status": "blacklist", "size": 5})
    assert all(x["status"] == "blacklist" and x["brand_id"] == 1 for x in r.json()["rows"])
    r = client.get("/api/members", headers=auth, params={"username": "agent001", "brand_id": 1})
    assert r.json()["total"] == 1


def test_member_tree(client, auth):
    agent = new_member(client, auth)
    child = new_member(client, auth, inviter=agent["username"])
    grand = new_member(client, auth, inviter=child["username"])
    assert grand["inviter_username"] == child["username"]
    assert grand["top_agent_username"] == agent["username"]
    d = client.get(f"/api/members/{agent['id']}", headers=auth).json()
    assert d["direct_invites"] == 1 and d["downline_total"] == 2
    down = client.get(f"/api/members/{agent['id']}/downline", headers=auth).json()
    assert {r["id"] for r in down["rows"]} == {child["id"], grand["id"]}


def test_status_bulk_and_audit(client, auth):
    a, b = new_member(client, auth), new_member(client, auth)
    r = client.post("/api/members/bulk-status", headers=auth,
                    json={"ids": [a["id"], b["id"]], "status": "blacklist"})
    assert r.json()["updated"] == 2
    r = client.patch(f"/api/members/{a['id']}/status", headers=auth, json={"status": "normal"})
    assert r.status_code == 200
    logs = client.get("/api/admin/audit-logs", headers=auth, params={"target_id": a["id"]}).json()
    assert any(l["action"] == "member.status_change" for l in logs["rows"])


def test_export(client, auth):
    r = client.get("/api/members/export", headers=auth, params={"brand_id": 1, "username_like": "agent00"})
    assert r.status_code == 200 and r.content[:2] == b"PK"  # xlsx is a zip


# ---------------------------------------------------------------- finance
def test_deposit_approve_with_commissions(client, auth):
    l1 = new_member(client, auth)
    l2 = new_member(client, auth, inviter=l1["username"])
    l3 = new_member(client, auth, inviter=l2["username"])
    user = new_member(client, auth, inviter=l3["username"])
    key = uuid.uuid4().hex
    body = {"member_id": user["id"], "channel_id": channel_id(client, auth), "amount": "100000",
            "request_key": key}
    dep = client.post("/api/finance/deposits", headers=auth, json=body).json()
    # same request_key again -> same request (idempotent)
    assert client.post("/api/finance/deposits", headers=auth, json=body).json()["id"] == dep["id"]

    r = client.post(f"/api/finance/deposits/{dep['id']}/approve", headers=auth, json={})
    assert r.status_code == 200, r.text
    assert balance(client, auth, user["id"])[0] == D(100000)
    assert balance(client, auth, l3["id"])[0] == D(2000)   # 2%
    assert balance(client, auth, l2["id"])[0] == D(1000)   # 1%
    assert balance(client, auth, l1["id"])[0] == D(500)    # 0.5%
    # approving twice is refused
    assert client.post(f"/api/finance/deposits/{dep['id']}/approve", headers=auth, json={}).status_code == 409


def test_deposit_limits_and_reject(client, auth):
    user = new_member(client, auth)
    r = client.post("/api/finance/deposits", headers=auth,
                    json={"member_id": user["id"], "channel_id": channel_id(client, auth), "amount": "10"})
    assert r.status_code == 400  # below channel minimum
    dep = client.post("/api/finance/deposits", headers=auth,
                      json={"member_id": user["id"], "channel_id": channel_id(client, auth),
                            "amount": "5000"}).json()
    r = client.post(f"/api/finance/deposits/{dep['id']}/reject", headers=auth, json={"note": "fake slip"})
    assert r.json()["status"] == "rejected"
    assert balance(client, auth, user["id"]) == (D(0), D(0))


def _fund(client, auth, member_id, amount):
    dep = client.post("/api/finance/deposits", headers=auth,
                      json={"member_id": member_id, "channel_id": channel_id(client, auth),
                            "amount": str(amount)}).json()
    client.post(f"/api/finance/deposits/{dep['id']}/approve", headers=auth, json={})


def test_withdraw_freeze_approve_reject(client, auth):
    user = new_member(client, auth)
    _fund(client, auth, user["id"], 50000)
    wd = {"member_id": user["id"], "receive_method": "kbzpay", "receive_account": "0900", "receive_name": "T"}

    r = client.post("/api/finance/withdrawals", headers=auth, json={**wd, "amount": "60000"})
    assert r.status_code == 400  # more than balance

    w1 = client.post("/api/finance/withdrawals", headers=auth, json={**wd, "amount": "30000"}).json()
    assert balance(client, auth, user["id"]) == (D(50000), D(30000))
    # only 20,000 is still available
    r = client.post("/api/finance/withdrawals", headers=auth, json={**wd, "amount": "25000"})
    assert r.status_code == 400

    client.post(f"/api/finance/withdrawals/{w1['id']}/approve", headers=auth, json={"payout_ref": "P1"})
    assert balance(client, auth, user["id"]) == (D(20000), D(0))

    w2 = client.post("/api/finance/withdrawals", headers=auth, json={**wd, "amount": "20000"}).json()
    client.post(f"/api/finance/withdrawals/{w2['id']}/reject", headers=auth, json={})
    assert balance(client, auth, user["id"]) == (D(20000), D(0))


def test_blacklisted_cannot_withdraw(client, auth):
    user = new_member(client, auth)
    _fund(client, auth, user["id"], 10000)
    client.patch(f"/api/members/{user['id']}/status", headers=auth, json={"status": "blacklist"})
    r = client.post("/api/finance/withdrawals", headers=auth,
                    json={"member_id": user["id"], "amount": "1000", "receive_method": "kbzpay",
                          "receive_account": "0900", "receive_name": "T"})
    assert r.status_code == 400


def test_adjust_and_ledger(client, auth):
    user = new_member(client, auth)
    client.post("/api/finance/adjust", headers=auth, json={"member_id": user["id"], "amount": "700", "note": "bonus"})
    r = client.post("/api/finance/adjust", headers=auth,
                    json={"member_id": user["id"], "amount": "-1000", "note": "too much"})
    assert r.status_code == 400
    led = client.get("/api/finance/transactions", headers=auth, params={"member_id": user["id"]}).json()
    assert led["total"] == 1 and D(led["rows"][0]["balance_after"]) == D(700)


def test_ledger_matches_wallets(client, auth):
    """Sum of ledger per member must equal wallet balance for everybody."""
    from app import db
    with db.pool.connection() as conn:
        bad = conn.execute(
            """SELECT w.member_id FROM wallets w
               LEFT JOIN (SELECT member_id, sum(amount) s FROM wallet_transactions GROUP BY 1) t
                 ON t.member_id = w.member_id
               WHERE w.balance <> COALESCE(t.s, 0)"""
        ).fetchall()
        assert bad == []
        try:
            conn.execute("DELETE FROM wallet_transactions WHERE id = (SELECT min(id) FROM wallet_transactions)")
            raise AssertionError("ledger delete should fail")
        except Exception as e:
            assert "append-only" in str(e)
            conn.rollback()


# ---------------------------------------------------------------- reports / admin / permissions
def test_reports(client, auth):
    s = client.get("/api/reports/summary", headers=auth).json()
    assert len(s) == 2 and D(s[0]["deposits"]) > 0
    d = client.get("/api/reports/daily", headers=auth, params={"brand_id": 1}).json()
    assert len(d) == 30


def test_marketing_role_is_limited(client, auth):
    roles = client.get("/api/admin/roles", headers=auth).json()
    mk = next(r["id"] for r in roles if r["name"] == "marketing")
    name = "mk_" + uuid.uuid4().hex[:8]
    r = client.post("/api/admin/users", headers=auth,
                    json={"username": name, "password": "password123", "role_id": mk, "allowed_brands": [2]})
    assert r.status_code == 201
    tok = client.post("/api/auth/login", json={"username": name, "password": "password123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    rows = client.get("/api/members", headers=h, params={"size": 20}).json()["rows"]
    assert rows and all(x["brand_id"] == 2 for x in rows)                  # only its brand
    assert client.get("/api/members", headers=h, params={"brand_id": 1}).status_code == 403
    assert client.get("/api/finance/deposits", headers=h).status_code == 403   # no finance
    assert client.get("/api/members/1", headers=h).status_code == 404         # brand 1 member hidden
