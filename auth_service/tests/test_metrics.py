from metrics import store_health


class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client, mock_store):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")


class TestStoreHealthGauge:
    def test_healthy_store_sets_one(self, client, mock_store):
        mock_store.health.return_value = True
        client.get("/readyz")
        resp = client.get("/metrics")
        assert "wicket_store_health 1.0" in resp.text

    def test_unhealthy_store_sets_zero(self, client, mock_store):
        store_health.set(1)
        mock_store.health.side_effect = Exception("boom")
        client.get("/readyz")
        resp = client.get("/metrics")
        assert "wicket_store_health 0.0" in resp.text
