class TestHealthz:
    def test_healthz_ok(self, client, mock_store):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_readyz_ok(self, client, mock_store):
        resp = client.get("/readyz")
        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_readyz_store_down(self, client, mock_store):
        mock_store.health.side_effect = Exception("boom")
        resp = client.get("/readyz")
        assert resp.status_code == 503
