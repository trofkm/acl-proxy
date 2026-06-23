from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError, TimeoutError

from config import Config


class RedisTokenStore:
    def __init__(self, cfg: Config) -> None:
        ssl_params = {}
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
            client_name=cfg.redis_client_name,
            retry=retry,
            retry_on_error=[ConnectionError, TimeoutError],
            **ssl_params,
        )

    async def get_token(self, token_hash: str) -> dict | None:
        token_data = await self._client.hgetall(f"tokens:{token_hash}")
        if not token_data:
            return None
        return dict(token_data)

    async def set_token(self, token_hash: str, data: dict, ttl: int = 0) -> None:
        key = f"tokens:{token_hash}"
        await self._client.hset(key, mapping=data)
        if ttl > 0:
            await self._client.expire(key, ttl)

    async def delete_token(self, token_hash: str) -> None:
        await self._client.delete(f"tokens:{token_hash}")

    async def list_tokens(self) -> list[dict]:
        keys = [key async for key in self._client.scan_iter("tokens:*")]
        if not keys:
            return []

        pipe = self._client.pipeline(transaction=False)
        for key in keys:
            pipe.hgetall(key)
            pipe.ttl(key)
        results = await pipe.execute()

        tokens: list[dict] = []
        for idx, key in enumerate(keys):
            token_hash = key.split(":", 1)[1]
            data = results[idx * 2]
            ttl_seconds = results[idx * 2 + 1]

            tokens.append(
                {
                    "token_hash": token_hash,
                    "hosts": data.get("hosts", ""),
                    "email": data.get("email", ""),
                    "comment": data.get("comment", ""),
                    "created_at_raw": data.get("created_at", ""),
                    "ttl": ttl_seconds,
                }
            )

        return tokens

    async def health(self) -> bool:
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.close()
