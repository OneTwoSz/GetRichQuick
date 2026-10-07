"""
Sign-in hardening: httpOnly session cookies, revocation, CSRF header,
brute-force limits, password policy, change and reset.
"""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import UserSession
from app.utils.timeutil import utcnow

GOOD = {"email": "owner@example.com", "password": "correct horse 42"}


def _login(client, creds=GOOD):
    return client.post("/api/auth/login", json=creds)


def _second_client():
    return TestClient(app, headers={"X-Requested-With": "test"})


def _db():
    return next(app.dependency_overrides[get_db]())


def test_login_sets_httponly_cookie_and_returns_no_token(auth_client):
    r = _login(auth_client)
    assert r.status_code == 200, r.text
    assert "access_token" not in r.json()            # nothing for page scripts to steal
    cookie = r.headers["set-cookie"].lower()
    assert "gt_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert auth_client.get("/api/auth/me").json()["email"] == "owner@example.com"


def test_email_is_case_insensitive(auth_client):
    assert _login(auth_client, {**GOOD, "email": "Owner@Example.com"}).status_code == 200


def test_unauthenticated_requests_get_401(auth_client):
    assert auth_client.get("/api/auth/me").status_code == 401
    assert auth_client.get("/api/products").status_code == 401


def test_state_changes_require_csrf_header(auth_client):
    bare = TestClient(app)  # no X-Requested-With
    assert bare.post("/api/auth/login", json=GOOD).status_code == 403
    assert bare.get("/health").status_code == 200   # reads are unaffected


def test_logout_really_ends_the_session(auth_client):
    _login(auth_client)
    token = auth_client.cookies.get("gt_session")
    assert auth_client.post("/api/auth/logout").status_code == 204
    replay = _second_client()
    replay.cookies.set("gt_session", token)
    assert replay.get("/api/auth/me").status_code == 401  # a copied cookie is dead too


def test_bearer_header_works_for_api_clients(auth_client):
    _login(auth_client)
    token = auth_client.cookies.get("gt_session")
    api = _second_client()
    assert api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_repeated_failures_lock_out_that_email(auth_client):
    for _ in range(5):
        assert _login(auth_client, {**GOOD, "password": "wrong password!"}).status_code == 401
    r = _login(auth_client)  # even the right password is refused for now
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_idle_sessions_expire(auth_client):
    _login(auth_client)
    db = _db()
    s = db.query(UserSession).first()
    s.last_seen_at = utcnow() - timedelta(days=20)
    db.commit()
    assert auth_client.get("/api/auth/me").status_code == 401


def test_sessions_can_be_listed_and_revoked(auth_client):
    _login(auth_client)
    phone = _second_client()
    _login(phone)
    sessions = auth_client.get("/api/auth/sessions").json()
    assert len(sessions) == 2
    assert sum(s["current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["current"])
    assert auth_client.delete(f"/api/auth/sessions/{other['id']}").status_code == 204
    assert phone.get("/api/auth/me").status_code == 401
    assert auth_client.get("/api/auth/me").status_code == 200


def test_logout_everywhere(auth_client):
    _login(auth_client)
    phone = _second_client()
    _login(phone)
    assert auth_client.post("/api/auth/logout-all").status_code == 204
    assert phone.get("/api/auth/me").status_code == 401
    assert auth_client.get("/api/auth/me").status_code == 401


def test_change_password_signs_out_other_devices(auth_client):
    _login(auth_client)
    phone = _second_client()
    _login(phone)
    bad = auth_client.post("/api/auth/change-password",
                           json={"current_password": "nope nope", "new_password": "a better pass 7"})
    assert bad.status_code == 400
    r = auth_client.post("/api/auth/change-password",
                         json={"current_password": GOOD["password"], "new_password": "a better pass 7"})
    assert r.status_code == 204, r.text
    assert auth_client.get("/api/auth/me").status_code == 200   # this device stays in
    assert phone.get("/api/auth/me").status_code == 401         # others are out
    assert _login(_second_client()).status_code == 401
    assert _login(_second_client(), {**GOOD, "password": "a better pass 7"}).status_code == 200


def test_password_policy_on_register(auth_client):
    weak = auth_client.post("/api/auth/register",
                            json={"email": "new@example.com", "name": "New", "password": "short"})
    assert weak.status_code == 400
    common = auth_client.post("/api/auth/register",
                              json={"email": "new@example.com", "name": "New", "password": "password123"})
    assert common.status_code == 400
    ok = auth_client.post("/api/auth/register",
                          json={"email": "New@Example.com", "name": "New", "password": "dye house 2026"})
    assert ok.status_code == 201, ok.text
    assert auth_client.get("/api/auth/me").json()["email"] == "new@example.com"  # signed in


def test_password_reset_flow(auth_client, monkeypatch):
    sent = []
    monkeypatch.setattr("app.routes.auth.send_email", lambda to, subject, body: sent.append(body) or True)
    _login(auth_client)

    unknown = auth_client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"})
    known = auth_client.post("/api/auth/password-reset/request", json={"email": "owner@example.com"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()   # no account enumeration
    assert len(sent) == 1
    token = sent[0].split("token=")[1].split()[0]

    weak = auth_client.post("/api/auth/password-reset/confirm", json={"token": token, "new_password": "abc"})
    assert weak.status_code == 400
    r = auth_client.post("/api/auth/password-reset/confirm",
                         json={"token": token, "new_password": "fresh start 99"})
    assert r.status_code == 204, r.text
    assert auth_client.get("/api/auth/me").status_code == 401    # every session ended
    reuse = auth_client.post("/api/auth/password-reset/confirm",
                             json={"token": token, "new_password": "another one 88"})
    assert reuse.status_code == 400                               # single use
    assert _login(auth_client, {**GOOD, "password": "fresh start 99"}).status_code == 200
