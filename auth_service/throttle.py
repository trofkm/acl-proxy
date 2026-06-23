"""Brute-force throttling for /auth and admin endpoints.

Tracks failed auth attempts per client IP with a sliding window.
Successful auths are never penalised — only 401 responses count.

Architecture mirrors storage.py: Protocol + two implementations.
- MemoryFailureStore: in-memory deque-based window, for single-instance (sqlite) deploys
- RedisFailureStore: Redis sorted-set with TTL, for multi-instance deploys
"""

import time
from collections import defaultdict, deque
from typing import Protocol, runtime_checkable

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from config import Config
from log import logger


@runtime_checkable
class FailureStore(Protocol):
    """Tracks auth failures per client IP using a sliding window.

    Implementations must be concurrency-safe: MemoryFailureStore relies on
    asyncio's single-threaded event loop; RedisFailureStore uses atomic
    Redis commands.
    """

    async def is_blocked(self, ip: str) -> bool:
        """Return True if this IP has exceeded the failure threshold."""
        ...

    async def record_failure(self, ip: str) -> None:
        """Record a failed auth attempt for this IP."""
        ...

    async def close(self) -> None:
        """Release resources (connection pools, etc.)."""
        ...


class MemoryFailureStore:
    """In-memory sliding-window failure tracker.

    Each IP maps to a deque of failure timestamps.  Window trimming
    happens on every ``is_blocked()`` call — old timestamps are popped
    from the left in O(1).  Stale IPs are garbage-collected lazily
    during ``record_failure()``.

    ``deque`` is the idiomatic Python choice for a sliding window
    (over ``list``) because ``popleft()`` is O(1), while ``list.pop(0)``
    shifts the entire array.
    """

    def __init__(
        self,
        window_seconds: int = 60,
        max_failures: int = 10,
        prune_age_seconds: float = 300.0,
    ) -> None:
        self._window = window_seconds
        self._max = max_failures
        self._prune_age = prune_age_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    async def is_blocked(self, ip: str) -> bool:
        now = time.time()
        bucket = self._buckets.get(ip)
        if bucket is None:
            return False

        cutoff = now - self._window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if not bucket:
            del self._buckets[ip]
            return False

        return len(bucket) >= self._max

    async def record_failure(self, ip: str) -> None:
        now = time.time()
        bucket = self._buckets[ip]
        bucket.append(now)

        recent = sum(1 for ts in bucket if ts > now - self._window)
        if recent >= self._max // 2:
            logger.warning(
                "throttle_failure_recorded",
                ip=ip,
                recent_failures=recent,
                max_failures=self._max,
            )

        self._prune(now)

    def _prune(self, now: float) -> None:
        cutoff = now - self._prune_age
        stale = [
            ip
            for ip, bucket in self._buckets.items()
            if not bucket or bucket[-1] < cutoff
        ]
        for ip in stale:
            del self._buckets[ip]

    async def close(self) -> None:
        self._buckets.clear()


class RedisFailureStore:
    """Redis-backed failure tracker using sorted sets.

    Key layout::

        throttle:{prefix}:{ip}  →  ZSET  {timestamp: timestamp, ...}  TTL = window × 2

    - ``ZREMRANGEBYSCORE`` prunes expired entries before counting.
    - ``EXPIRE`` ensures the key auto-deletes after twice the window
      (so an IP that goes quiet doesn't leak keys).
    - All Redis commands are atomic — safe for multi-replica deploys.
    """

    def __init__(
        self,
        cfg: Config,
        prefix: str = "auth",
        window_seconds: int = 60,
        max_failures: int = 10,
    ) -> None:
        self._prefix = prefix
        self._window = window_seconds
        self._max = max_failures

        ssl_params: dict = {}
        if cfg.redis_tls:
            ssl_params["ssl"] = True
            ssl_params["ssl_cert_reqs"] = (
                None if cfg.redis_tls_skip_verify else "required"
            )
            if cfg.redis_tls_skip_verify:
                ssl_params["ssl_check_hostname"] = False
            if cfg.redis_ca_certs:
                ssl_params["ssl_ca_certs"] = cfg.redis_ca_certs

        retry = None
        if cfg.redis_retry_count > 0:
            retry = Retry(
                backoff=ExponentialBackoff(),
                retries=cfg.redis_retry_count,
            )

        self._client = Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            db=cfg.redis_db,
            username=cfg.redis_username,
            password=cfg.redis_password,
            decode_responses=True,
            socket_timeout=cfg.redis_socket_timeout,
            socket_connect_timeout=cfg.redis_socket_connect_timeout,
            max_connections=cfg.redis_max_connections,
            health_check_interval=cfg.redis_health_check_interval,
            client_name=f"{cfg.redis_client_name}-{prefix}-throttle",
            retry=retry,
            retry_on_error=[RedisConnectionError, RedisTimeoutError],
            **ssl_params,
        )

    async def is_blocked(self, ip: str) -> bool:
        try:
            key = f"throttle:{self._prefix}:{ip}"
            now = time.time()
            cutoff = now - self._window

            await self._client.zremrangebyscore(key, "-inf", cutoff)
            count = await self._client.zcard(key)
            return count >= self._max
        except Exception:
            logger.warning("throttle_redis_error", ip=ip, exc_info=True)
            return False

    async def record_failure(self, ip: str) -> None:
        try:
            key = f"throttle:{self._prefix}:{ip}"
            now = time.time()
            await self._client.zadd(key, {str(now): now})
            await self._client.expire(key, self._window * 2)
        except Exception:
            logger.warning("throttle_redis_error", ip=ip, exc_info=True)

    async def close(self) -> None:
        await self._client.close()
