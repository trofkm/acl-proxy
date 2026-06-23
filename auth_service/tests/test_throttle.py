import asyncio
import time

import pytest

from main import app
from tests.helpers import basic_auth_headers
from throttle import MemoryFailureStore


def _run(coro):
    return asyncio.run(coro)


class TestMemoryFailureStore:
    def test_not_blocked_with_no_history(self):
        store = MemoryFailureStore(window_seconds=60, max_failures=10)
        assert not _run(store.is_blocked("1.2.3.4"))

    def test_not_blocked_below_threshold(self):
        store = MemoryFailureStore(window_seconds=60, max_failures=10)
        for _ in range(9):
            _run(store.record_failure("1.2.3.4"))
        assert not _run(store.is_blocked("1.2.3.4"))

    def test_blocked_at_threshold(self):
        store = MemoryFailureStore(window_seconds=60, max_failures=3)
        for _ in range(3):
            _run(store.record_failure("1.2.3.4"))
        assert _run(store.is_blocked("1.2.3.4"))

    def test_window_expires(self):
        store = MemoryFailureStore(window_seconds=1, max_failures=3)
        for _ in range(3):
            _run(store.record_failure("1.2.3.4"))
        assert _run(store.is_blocked("1.2.3.4"))

        time.sleep(1.1)
        assert not _run(store.is_blocked("1.2.3.4"))

    def test_window_trimming_on_is_blocked(self):
        store = MemoryFailureStore(window_seconds=60, max_failures=5)
        store._buckets["1.2.3.4"].append(time.time() - 120)
        _run(store.record_failure("1.2.3.4"))
        assert not _run(store.is_blocked("1.2.3.4"))

    def test_per_ip_isolation(self):
        store = MemoryFailureStore(window_seconds=60, max_failures=3)
        for _ in range(3):
            _run(store.record_failure("1.2.3.4"))
        assert _run(store.is_blocked("1.2.3.4"))
        assert not _run(store.is_blocked("5.6.7.8"))

    def test_prune_removes_stale_ips(self):
        store = MemoryFailureStore(
            window_seconds=60, max_failures=10, prune_age_seconds=0.01
        )
        store._buckets["1.2.3.4"].append(time.time() - 10)
        _run(store.record_failure("5.6.7.8"))
        assert "1.2.3.4" not in store._buckets

    def test_close_clears_buckets(self):
        store = MemoryFailureStore()
        _run(store.record_failure("1.2.3.4"))
        assert len(store._buckets) > 0
        _run(store.close())
        assert len(store._buckets) == 0


@pytest.fixture
def strict_throttle(client):
    app.state.auth_throttle = MemoryFailureStore(window_seconds=60, max_failures=3)
    app.state.admin_throttle = MemoryFailureStore(window_seconds=60, max_failures=3)


class TestAuthThrottle:
    def test_200_not_penalised(self, client, mock_store, strict_throttle):
        mock_store.get_token.return_value = {"hosts": "example.com"}
        headers = {
            "Authorization": "Bearer my-token",
            "X-Forwarded-Host": "example.com",
        }
        for _ in range(100):
            resp = client.get("/auth", headers=headers)
            assert resp.status_code == 200

    def test_429_after_too_many_failures(self, client, mock_store, strict_throttle):
        mock_store.get_token.return_value = None
        headers = {
            "Authorization": "Bearer garbage",
            "X-Forwarded-Host": "example.com",
        }

        for i in range(3):
            resp = client.get("/auth", headers=headers)
            assert resp.status_code == 401, f"request {i + 1} should be 401"

        resp = client.get("/auth", headers=headers)
        assert resp.status_code == 429
        assert resp.headers["retry-after"] == "60"
        assert "too many failed" in resp.json()["detail"]

    def test_throttle_per_ip(self, client, mock_store, strict_throttle):
        mock_store.get_token.return_value = None

        headers_a = {
            "Authorization": "Bearer garbage",
            "X-Forwarded-Host": "example.com",
            "X-Forwarded-For": "1.2.3.4",
        }
        for _ in range(3):
            client.get("/auth", headers=headers_a)
        assert client.get("/auth", headers=headers_a).status_code == 429

        headers_b = {
            "Authorization": "Bearer garbage",
            "X-Forwarded-Host": "example.com",
            "X-Forwarded-For": "5.6.7.8",
        }
        resp = client.get("/auth", headers=headers_b)
        assert resp.status_code == 401

    def test_401_counts_as_failure(self, client, mock_store, strict_throttle):
        mock_store.get_token.return_value = {"hosts": "allowed.com"}
        headers = {
            "Authorization": "Bearer my-token",
            "X-Forwarded-Host": "evil.com",
        }

        for _ in range(3):
            resp = client.get("/auth", headers=headers)
            assert resp.status_code == 401

        resp = client.get("/auth", headers=headers)
        assert resp.status_code == 429

    def test_mixed_failures_count_together(self, client, mock_store, strict_throttle):
        headers = {
            "X-Forwarded-Host": "example.com",
        }

        headers["Authorization"] = ""
        client.get("/auth", headers=headers)
        client.get("/auth", headers=headers)

        mock_store.get_token.return_value = {"hosts": "allowed.com"}
        headers["Authorization"] = "Bearer my-token"
        resp = client.get("/auth", headers=headers)
        assert resp.status_code == 401

        headers["Authorization"] = ""
        resp = client.get("/auth", headers=headers)
        assert resp.status_code == 429


class TestAdminThrottle:
    def test_admin_200_not_penalised(self, client, mock_store, strict_throttle):
        for _ in range(100):
            resp = client.get("/", headers=basic_auth_headers())
            assert resp.status_code == 200

    def test_admin_429_after_too_many_failures(
        self, client, mock_store, strict_throttle
    ):
        bad = basic_auth_headers(password="wrong-pass")
        for i in range(3):
            resp = client.get("/", headers=bad)
            assert resp.status_code == 401, f"request {i + 1} should be 401"

        resp = client.get("/", headers=bad)
        assert resp.status_code == 429
        assert resp.headers["retry-after"] == "60"
        assert "too many failed" in resp.json()["detail"]

    def test_admin_throttle_per_ip(self, client, mock_store, strict_throttle):
        bad = basic_auth_headers(password="wrong-pass")

        headers_a = {**bad, "X-Forwarded-For": "1.2.3.4"}
        for _ in range(3):
            client.get("/", headers=headers_a)
        assert client.get("/", headers=headers_a).status_code == 429

        headers_b = {**bad, "X-Forwarded-For": "5.6.7.8"}
        resp = client.get("/", headers=headers_b)
        assert resp.status_code == 401


class TestCrossContamination:
    def test_admin_failures_do_not_block_auth(
        self, client, mock_store, strict_throttle
    ):
        bad_admin = basic_auth_headers(password="wrong-pass")
        for _ in range(3):
            client.get("/", headers=bad_admin)
        assert client.get("/", headers=bad_admin).status_code == 429

        mock_store.get_token.return_value = {"hosts": "example.com"}
        auth_headers = {
            "Authorization": "Bearer my-token",
            "X-Forwarded-Host": "example.com",
        }
        resp = client.get("/auth", headers=auth_headers)
        assert resp.status_code == 200

    def test_auth_failures_do_not_block_admin(
        self, client, mock_store, strict_throttle
    ):
        mock_store.get_token.return_value = None
        bad_auth = {
            "Authorization": "Bearer garbage",
            "X-Forwarded-Host": "example.com",
        }
        for _ in range(3):
            client.get("/auth", headers=bad_auth)
        assert client.get("/auth", headers=bad_auth).status_code == 429

        resp = client.get("/", headers=basic_auth_headers())
        assert resp.status_code == 200
