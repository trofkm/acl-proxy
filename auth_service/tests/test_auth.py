class TestAuthEndpoint:
    def test_no_auth_header(self, client, mock_store):
        resp = client.get("/auth", headers={"X-Forwarded-Host": "example.com"})
        assert resp.status_code == 401

    def test_not_bearer(self, client, mock_store):
        resp = client.get(
            "/auth",
            headers={
                "Authorization": "Basic xyz",
                "X-Forwarded-Host": "example.com",
            },
        )
        assert resp.status_code == 401

    def test_empty_token(self, client, mock_store):
        resp = client.get(
            "/auth",
            headers={
                "Authorization": "Bearer ",
                "X-Forwarded-Host": "example.com",
            },
        )
        assert resp.status_code == 401

    def test_missing_x_forwarded_host(self, client, mock_store):
        resp = client.get("/auth", headers={"Authorization": "Bearer some-token"})
        assert resp.status_code == 400
        assert "X-Forwarded-Host" in resp.json()["detail"]

    def test_invalid_token(self, client, mock_store):
        mock_store.get_token.return_value = None
        resp = client.get(
            "/auth",
            headers={
                "Authorization": "Bearer garbage",
                "X-Forwarded-Host": "example.com",
            },
        )
        assert resp.status_code == 401

    def test_valid_token_wrong_host(self, client, mock_store):
        mock_store.get_token.return_value = {"hosts": "allowed.com"}
        resp = client.get(
            "/auth",
            headers={
                "Authorization": "Bearer my-token",
                "X-Forwarded-Host": "evil.com",
            },
        )
        assert resp.status_code == 401

    def test_valid_token_correct_host(self, client, mock_store):
        mock_store.get_token.return_value = {"hosts": "example.com"}
        resp = client.get(
            "/auth",
            headers={
                "Authorization": "Bearer my-token",
                "X-Forwarded-Host": "example.com",
            },
        )
        assert resp.status_code == 200

    def test_token_with_no_hosts(self, client, mock_store):
        mock_store.get_token.return_value = {"hosts": ""}
        resp = client.get(
            "/auth",
            headers={
                "Authorization": "Bearer my-token",
                "X-Forwarded-Host": "example.com",
            },
        )
        assert resp.status_code == 401

    def test_post_method_accepted(self, client, mock_store):
        mock_store.get_token.return_value = {"hosts": "example.com"}
        resp = client.post(
            "/auth",
            headers={
                "Authorization": "Bearer my-token",
                "X-Forwarded-Host": "example.com",
            },
        )
        assert resp.status_code == 200
