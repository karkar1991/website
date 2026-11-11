import io
import time
import uuid
from decimal import Decimal

import pyotp
from openpyxl import Workbook

from test_api import channel_id, new_member


def _admin(client, auth, role="super_admin", brands=(1, 2)):
    roles = client.get("/api/admin/roles", headers=auth).json()
    rid = next(r["id"] for r in roles if r["name"] == role)
    name = "a_" + uuid.uuid4().hex[:8]
    r = client.post("/api/admin/users", headers=auth,
                    json={"username": name, "password": "password123", "role_id": rid, "allowed_brands": list(brands)})
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, username, password="password123", otp=None):
    return client.post("/api/auth/login", json={"username": username, "password": password, "otp": otp})


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- options / filters / edit
def test_options_have_new_lists(client, auth):
    o = client.get("/api/options", headers=auth).json()
    assert o["member_levels"] and o["sources"] and o["account_types"] == ["formal", "test"]


def test_filters_account_type_level_source(client, auth):
    r = client.get("/api/members", headers=auth, params={"brand_id": 1, "account_type": "test", "size": 5}).json()
    assert r["total"] > 0 and all(x["account_type"] == "test" for x in r["rows"])
    src = next(s for s in client.get("/api/options", headers=auth).json()["sources"] if s["brand_id"] == 1)
    r = client.get("/api/members", headers=auth, params={"source_id": src["id"], "size": 5}).json()
    assert r["total"] > 0 and all(x["source_name"] == src["name"] for x in r["rows"])


def test_edit_member(client, auth):
    m = new_member(client, auth)
    lv = next(x for x in client.get("/api/options", headers=auth).json()["member_levels"]
              if x["brand_id"] == 1 and x["name"] == "Premium")
    r = client.patch(f"/api/members/{m['id']}", headers=auth,
                     json={"full_name": "Edited", "account_type": "test", "member_level_id": lv["id"]})
    assert r.status_code == 200
    d = client.get(f"/api/members/{m['id']}", headers=auth).json()
    assert d["full_name"] == "Edited" and d["account_type"] == "test" and d["member_level"] == "Premium"
    # level from another brand is refused
    other = next(x for x in client.get("/api/options", headers=auth).json()["member_levels"] if x["brand_id"] == 2)
    assert client.patch(f"/api/members/{m['id']}", headers=auth,
                        json={"member_level_id": other["id"]}).status_code == 400


def test_children_paging(client, auth):
    agent = new_member(client, auth)
    for _ in range(3):
        new_member(client, auth, inviter=agent["username"])
    r = client.get(f"/api/members/{agent['id']}/children", headers=auth, params={"size": 2}).json()
    assert len(r["rows"]) == 2 and r["has_more"] is True
    r = client.get(f"/api/members/{agent['id']}/children", headers=auth, params={"size": 2, "page": 2}).json()
    assert len(r["rows"]) == 1 and r["has_more"] is False


# ---------------------------------------------------------------- import
def test_import_validates_then_imports(client, auth):
    agent = new_member(client, auth)
    p = uuid.uuid4().hex[:6]
    bad = _xlsx([
        ["username", "full_name", "inviter_username", "member_level", "source_code"],
        [f"im_{p}_a", "A", agent["username"], "Free", "facebook"],
        [f"im_{p}_b", "B", f"im_{p}_a", "Free", "nope"],          # unknown source
        [f"im_{p}_a", "dup", "", "", ""],                            # duplicate in file
        ["x", "short", "", "", ""],                                  # bad username
        [f"im_{p}_c", "C", "ghost_user_zzz", "", ""],                # unknown inviter
    ])
    files = {"file": ("m.xlsx", bad, "application/octet-stream")}
    r = client.post("/api/members/import", headers=auth, data={"brand_id": 1, "dry_run": "false"}, files=files)
    body = r.json()
    assert body["imported"] == 0 and body["error_count"] == 4
    assert client.get("/api/members", headers=auth, params={"brand_id": 1, "username": f"im_{p}_a"}).json()["total"] == 0

    good = (f"username,full_name,phone,inviter_username,account_type,vip_level,member_level,source_code\n"
            f"im_{p}_a,A,0911,{agent['username']},formal,0,Free,facebook\n"
            f"im_{p}_b,B,0922,im_{p}_a,test,1,Basic,tiktok\n").encode()
    files = {"file": ("m.csv", good, "text/csv")}
    dry = client.post("/api/members/import", headers=auth, data={"brand_id": 1}, files=files).json()
    assert dry["valid_rows"] == 2 and dry["imported"] == 0
    files = {"file": ("m.csv", good, "text/csv")}
    r = client.post("/api/members/import", headers=auth, data={"brand_id": 1, "dry_run": "false"}, files=files).json()
    assert r["imported"] == 2
    b = client.get("/api/members", headers=auth, params={"brand_id": 1, "username": f"im_{p}_b"}).json()["rows"][0]
    assert b["inviter_username"] == f"im_{p}_a" and b["top_agent_username"] == agent["username"]
    assert b["account_type"] == "test" and b["vip_name"] == "VIP1" and b["source_name"] == "TikTok"


def test_import_template(client, auth):
    r = client.get("/api/members/import-template", headers=auth)
    assert r.status_code == 200 and r.content[:2] == b"PK"


# ---------------------------------------------------------------- agents
def test_agents_stats(client, auth):
    agent = new_member(client, auth)
    child = new_member(client, auth, inviter=agent["username"])
    grand = new_member(client, auth, inviter=child["username"])
    dep = client.post("/api/finance/deposits", headers=auth,
                      json={"member_id": grand["id"], "channel_id": channel_id(client, auth), "amount": "100000"}).json()
    client.post(f"/api/finance/deposits/{dep['id']}/approve", headers=auth, json={})
    r = client.get("/api/agents", headers=auth, params={"brand_id": 1, "username": agent["username"]}).json()
    a = r["rows"][0]
    assert a["direct"] == 1 and a["downline"] == 2 and a["new_members"] == 2
    assert Decimal(str(a["deposits"])) == Decimal(100000) and Decimal(str(a["commission"])) == Decimal(1000)


def test_agents_list_fast_enough(client, auth):
    for sort in ("direct", "deposits"):
        t = time.time()
        r = client.get("/api/agents", headers=auth, params={"brand_id": 1, "top_only": sort == "deposits",
                                                              "sort": sort})
        assert r.status_code == 200 and r.json()["rows"]
        assert time.time() - t < 5, f"agents sort={sort} too slow"


# ---------------------------------------------------------------- sources + reports
def test_sources_crud_and_report(client, auth):
    code = "src_" + uuid.uuid4().hex[:6]
    s = client.post("/api/sources", headers=auth, json={"brand_id": 1, "code": code, "name": "Test src"}).json()
    assert client.post("/api/sources", headers=auth,
                       json={"brand_id": 1, "code": code, "name": "dup"}).status_code == 409
    client.post("/api/members", headers=auth,
                json={"brand_id": 1, "username": "s_" + uuid.uuid4().hex[:8], "source_id": s["id"]})
    rep = client.get("/api/reports/sources", headers=auth, params={"brand_id": 1}).json()
    assert any(r["code"] == code and r["new_members"] == 1 for r in rep)
    assert client.patch(f"/api/sources/{s['id']}", headers=auth, json={"is_active": False}).json()["is_active"] is False


def test_reports_exclude_test_accounts(client, auth):
    real = client.get("/api/reports/summary", headers=auth, params={"brand_id": 1}).json()[0]
    allm = client.get("/api/reports/summary", headers=auth, params={"brand_id": 1, "include_test": True}).json()[0]
    assert allm["total_members"] > real["total_members"]


# ---------------------------------------------------------------- notifications
def test_notifications(client, auth):
    n = client.get("/api/notifications", headers=auth).json()
    assert n["pending_deposits"] > 0 and n["latest"]
    mk = _admin(client, auth, role="marketing")
    tok = _login(client, mk["username"]).json()["access_token"]
    n = client.get("/api/notifications", headers={"Authorization": f"Bearer {tok}"}).json()
    assert n["pending_deposits"] == 0  # marketing has no finance access


# ---------------------------------------------------------------- login security
def test_lockout_after_failed_logins(client, auth):
    a = _admin(client, auth)
    for _ in range(5):
        assert _login(client, a["username"], "wrong-pass").status_code == 401
    r = _login(client, a["username"])  # right password, but locked
    assert r.status_code == 423
    client.patch(f"/api/admin/users/{a['id']}", headers=auth, json={"unlock": True})
    assert _login(client, a["username"]).status_code == 200


def test_two_factor_flow(client, auth):
    a = _admin(client, auth)
    h = {"Authorization": f"Bearer {_login(client, a['username']).json()['access_token']}"}
    setup = client.post("/api/auth/2fa/setup", headers=h).json()
    totp = pyotp.TOTP(setup["secret"])
    assert client.post("/api/auth/2fa/enable", headers=h, json={"code": "000000"}).status_code == 400
    assert client.post("/api/auth/2fa/enable", headers=h, json={"code": totp.now()}).status_code == 200
    assert client.get("/api/auth/me", headers=h).json()["totp_enabled"] is True

    r = _login(client, a["username"])
    assert r.status_code == 401 and r.json()["detail"] == "OTP_REQUIRED"
    assert _login(client, a["username"], otp="123456").status_code == 401
    assert _login(client, a["username"], otp=totp.now()).status_code == 200

    # super admin resets 2FA (lost phone)
    client.patch(f"/api/admin/users/{a['id']}", headers=auth, json={"reset_2fa": True})
    assert _login(client, a["username"]).status_code == 200
