import pytest

from tests.helpers import basic_auth_headers

_VALID_HASH = "a" * 64


class TestCreateToken:
    def test_valid(self, client, mock_store):
        resp = client.post(
            "/api/tokens",
            json={"hosts": "example.com"},
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert len(data["token"]) > 0
        mock_store.set_token.assert_called_once()
        args = mock_store.set_token.call_args[0]
        assert len(args[0]) == 64
        assert args[1]["hosts"] == "example.com"
        assert args[2] == 0

    def test_with_ttl(self, client, mock_store):
        resp = client.post(
            "/api/tokens",
            json={"hosts": "example.com", "ttl_seconds": 3600},
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 201
        mock_store.set_token.assert_called_once()
        assert mock_store.set_token.call_args[0][2] == 3600

    def test_with_email_and_comment(self, client, mock_store):
        resp = client.post(
            "/api/tokens",
            json={
                "hosts": "example.com",
                "email": "friend@example.com",
                "comment": "for Bob",
            },
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 201
        data = mock_store.set_token.call_args[0][1]
        assert data["email"] == "friend@example.com"
        assert data["comment"] == "for Bob"

    @pytest.mark.parametrize("ttl_input", ["not-a-number", -1, -3600])
    def test_invalid_ttl(self, client, mock_store, ttl_input):
        resp = client.post(
            "/api/tokens",
            json={"hosts": "example.com", "ttl_seconds": ttl_input},
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "hosts_input",
        [
            "example.com",
            "example.com,other.com",
            "  EXAMPLE.com , other.COM ",
            "*.example.com",
            "example.com:8080",
            "192.168.1.1:3000",
            "*.example.com:443",
            "*",
            "*:8080",
            "[::1]:9090",
            "api.example.com,*.other.com:3000",
        ],
    )
    def test_valid_hosts(self, client, mock_store, hosts_input):
        resp = client.post(
            "/api/tokens",
            json={"hosts": hosts_input},
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 201

    @pytest.mark.parametrize(
        "hosts_input",
        [
            " , ,,",
            "!!!bad!!!.com",
            "-bad.com",
            "bad-.com",
            "",
            "   ",
            "*.*.example.com",
            "example.com:99999",
            "example.com:0",
            ":8080",
            "foo.*.example.com",
        ],
    )
    def test_invalid_hosts(self, client, mock_store, hosts_input):
        resp = client.post(
            "/api/tokens",
            json={"hosts": hosts_input},
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 422

    def test_hosts_too_long(self, client, mock_store):
        resp = client.post(
            "/api/tokens",
            json={"hosts": "x" * 4097},
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 422

    def test_comment_too_long(self, client, mock_store):
        resp = client.post(
            "/api/tokens",
            json={"hosts": "example.com", "comment": "x" * 257},
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 422


class TestDeleteToken:
    def test_valid(self, client, mock_store):
        resp = client.delete(
            f"/api/tokens/{_VALID_HASH}",
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 204
        mock_store.delete_token.assert_called_once_with(_VALID_HASH)

    def test_invalid_hash_format(self, client, mock_store):
        resp = client.delete(
            "/api/tokens/not-hex!!",
            headers=basic_auth_headers(),
        )
        assert resp.status_code == 422
        mock_store.delete_token.assert_not_called()


class TestListTokens:
    def test_empty_list(self, client, mock_store):
        mock_store.list_tokens.return_value = []
        resp = client.get("/api/tokens", headers=basic_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["tokens"] == []
        assert data["total"] == 0

    def test_pagination(self, client, mock_store):
        raw = [
            {
                "token_hash": f"{'a' * 64}",
                "hosts": "host1.com",
                "email": "",
                "comment": "",
                "created_at_raw": "1000",
                "ttl": -1,
            },
            {
                "token_hash": f"{'b' * 64}",
                "hosts": "host2.com",
                "email": "",
                "comment": "",
                "created_at_raw": "2000",
                "ttl": -1,
            },
            {
                "token_hash": f"{'c' * 64}",
                "hosts": "host3.com",
                "email": "",
                "comment": "",
                "created_at_raw": "3000",
                "ttl": -1,
            },
        ]
        mock_store.list_tokens.return_value = raw

        resp = client.get("/api/tokens?page=1&size=2", headers=basic_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tokens"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1

        resp = client.get("/api/tokens?page=2&size=2", headers=basic_auth_headers())
        data = resp.json()
        assert len(data["tokens"]) == 1
        assert data["page"] == 2

    def test_default_page_size(self, client, mock_store):
        mock_store.list_tokens.return_value = []
        resp = client.get("/api/tokens", headers=basic_auth_headers())
        data = resp.json()
        assert data["page"] == 1
        assert data["size"] == 20

    def test_invalid_page(self, client, mock_store):
        resp = client.get("/api/tokens?page=0", headers=basic_auth_headers())
        assert resp.status_code == 422

    def test_invalid_size(self, client, mock_store):
        resp = client.get("/api/tokens?size=200", headers=basic_auth_headers())
        assert resp.status_code == 422
