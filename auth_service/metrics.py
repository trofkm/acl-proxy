from prometheus_client import Gauge

store_health = Gauge(
    "wicket_store_health",
    "Storage backend health (1 = reachable, 0 = unreachable)",
)
