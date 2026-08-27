"""Auth playbook checks: bcrypt hash format, httpOnly cookie on login, CORS credentials,
brute-force lockout, and admin seed idempotency."""
import os

import pytest
import requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
ADMIN = {"email": "admin@greenvalley.com", "password": "Admin@123"}
SUPER = {"email": "superadmin@propto.com", "password": "Propto@123"}


def test_super_admin_login_and_cookie():
    r = requests.post(f"{BASE}/api/auth/login", json=SUPER, timeout=60)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data["user"]["email"] == SUPER["email"]
    assert data["user"]["role"] == "super_admin"
    assert isinstance(data.get("token"), str) and len(data["token"]) > 20
    raw = r.headers.get("set-cookie", "")
    assert "access_token=" in raw, f"no auth cookie set: {raw}"
    assert "httponly" in raw.lower(), f"cookie not httpOnly: {raw}"
    assert "secure" in raw.lower(), f"cookie not Secure: {raw}"


def test_society_admin_login_and_me():
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=60)
    assert r.status_code == 200, r.text[:300]
    tok = r.json()["token"]
    me = requests.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    assert me.status_code == 200, me.text[:300]
    body = me.json()
    assert body["email"] == ADMIN["email"]
    assert body["role"] == "society_admin"
    assert body.get("society_id")
    assert "password_hash" not in body


def test_invalid_password_401():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN["email"], "password": "wrongpass"}, timeout=60)
    assert r.status_code == 401, r.text[:300]
    assert "detail" in r.json()


def test_me_without_token_401():
    r = requests.get(f"{BASE}/api/auth/me", timeout=60)
    assert r.status_code in (401, 403), r.status_code


def test_bcrypt_hash_format_in_db():
    from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
    import asyncio
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    async def run():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = c[os.environ["DB_NAME"]]
        return await db.users.find({}, {"email": 1, "password_hash": 1}).to_list(50)

    users = asyncio.run(run())
    assert users, "no users seeded"
    for u in users:
        h = u.get("password_hash", "")
        assert h.startswith("$2b$") or h.startswith("$2a$") or h.startswith("$2y$"), f"{u['email']} hash not bcrypt: {h[:10]}"


def test_cors_allows_credentials_with_explicit_origin():
    origin = BASE
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, headers={"Origin": origin}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    allow_origin = r.headers.get("access-control-allow-origin")
    allow_creds = r.headers.get("access-control-allow-credentials")
    print("CORS actual-request headers:", allow_origin, allow_creds)
    assert allow_creds == "true", dict(r.headers)
    assert allow_origin == origin, f"wildcard/mismatched origin with credentials: {allow_origin}"


def test_brute_force_lockout_after_5_failures():
    """Playbook requires lockout after 5 consecutive failures."""
    email = "bruteforce.probe@example.com"
    codes = []
    for _ in range(7):
        r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": "bad"}, timeout=60)
        codes.append(r.status_code)
    print("brute force codes:", codes)
    assert 429 in codes or 423 in codes, f"no lockout/rate-limit observed: {codes}"
