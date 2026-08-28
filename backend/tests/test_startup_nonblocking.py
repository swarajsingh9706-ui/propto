"""Iteration 7: verify startup() is fire-and-forget so serving never blocks on seeding.

Restarts the backend via supervisor, then measures how fast the very first request is
served, and verifies the backgrounded _seed_all() still completed (login + dashboard).
"""
import os
import subprocess
import time

import pytest
import requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
if not BASE:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

WHAPI = f"{BASE}/api/whapi/webhook"


@pytest.fixture(scope="module")
def restarted_backend():
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True, text=True, timeout=120)
    # wait for the process to accept connections (does NOT wait for seeding)
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/api/health", timeout=5)
            if r.status_code == 200:
                return time.time()
        except Exception:
            pass
        time.sleep(0.5)
    pytest.fail("backend did not come up within 60s after restart")


class TestNonBlockingStartup:
    def test_health_fast_after_restart(self, restarted_backend):
        t0 = time.time()
        r = requests.get(f"{BASE}/api/health", timeout=10)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("status") == "healthy", r.json()
        print(f"HEALTH_LATENCY={elapsed:.3f}s")
        assert elapsed < 3, f"health slow right after restart: {elapsed:.2f}s"

    def test_webhook_get_fast_after_restart(self, restarted_backend):
        t0 = time.time()
        r = requests.get(WHAPI, timeout=15)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text[:200]
        assert "live" in (r.json().get("detail") or "").lower(), r.json()
        print(f"WEBHOOK_GET_LATENCY={elapsed:.3f}s")
        assert elapsed < 5, f"webhook GET slow right after restart: {elapsed:.2f}s"

    def test_webhook_post_fast_after_restart(self, restarted_backend):
        t0 = time.time()
        r = requests.post(WHAPI, json={}, timeout=15)
        elapsed = time.time() - t0
        assert r.status_code == 200 and r.json() == {"status": "ok"}, r.text[:200]
        print(f"WEBHOOK_POST_LATENCY={elapsed:.3f}s")
        assert elapsed < 5, f"webhook POST slow right after restart: {elapsed:.2f}s"

    def test_seeding_completed_in_background(self, restarted_backend):
        """Backgrounded seeding must still finish: admin login + dashboard with real stats."""
        last = None
        for _ in range(20):
            r = requests.post(f"{BASE}/api/auth/login",
                              json={"email": "admin@greenvalley.com", "password": "Admin@123"}, timeout=30)
            last = r
            if r.status_code == 200:
                break
            time.sleep(1)
        assert last.status_code == 200, f"seeded admin unavailable after restart: {last.status_code} {last.text[:200]}"
        token = last.json().get("token")
        assert token
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {token}"})
        d = s.get(f"{BASE}/api/society/dashboard", timeout=30)
        assert d.status_code == 200, d.text[:200]
        data = d.json()
        print("DASHBOARD_AFTER_RESTART:", data)
        assert isinstance(data, dict) and data

    def test_no_startup_seeding_error_in_logs(self, restarted_backend):
        out = subprocess.run(["tail", "-n", "300", "/var/log/supervisor/backend.err.log"],
                             capture_output=True, text=True, timeout=60).stdout
        assert "startup seeding failed" not in out, out[-1500:]
