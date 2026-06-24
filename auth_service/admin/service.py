import secrets
import time

from auth.service import hash_token
from log import logger
from storage import TokenStore


def _format_tokens(raw_tokens: list[dict]) -> list[dict]:
    tokens: list[dict] = []
    for t in raw_tokens:
        created_raw = t.get("created_at_raw", "")
        created_iso = ""
        created_ts = 0
        if created_raw:
            try:
                created_ts = int(created_raw)
                created_iso = time.strftime("%Y-%m-%d %H:%M", time.gmtime(created_ts))
            except Exception:
                created_iso = ""
        tokens.append(
            {
                "token": t["token_hash"],
                "hosts": t.get("hosts", ""),
                "email": t.get("email", ""),
                "comment": t.get("comment", ""),
                "created_at": created_iso,
                "_created_ts": created_ts,
                "ttl": t.get("ttl", -1),
            }
        )
    tokens.sort(key=lambda t: t.get("_created_ts", 0))
    return tokens


async def list_tokens(store: TokenStore, page: int = 1, size: int = 20) -> dict:
    raw_tokens = await store.list_tokens()
    formatted = _format_tokens(raw_tokens)
    total = len(formatted)
    start = (page - 1) * size
    return {
        "tokens": formatted[start : start + size],
        "page": page,
        "size": size,
        "total": total,
    }


async def create_token(
    store: TokenStore,
    hosts: str,
    pepper: str,
    default_ttl: int = 0,
    ttl_seconds: int | None = None,
    email: str | None = None,
    comment: str | None = None,
) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash_value = hash_token(raw_token, pepper)

    logger.info(
        "token created: hosts=%s email=%s ttl=%s",
        hosts,
        email or "-",
        ttl_seconds or "default",
    )

    parsed_ttl: int = 0
    if ttl_seconds is not None:
        parsed_ttl = ttl_seconds
    ttl_effective = parsed_ttl if parsed_ttl > 0 else default_ttl

    data = {
        "hosts": hosts,
        "email": email or "",
        "comment": comment or "",
        "created_at": str(int(time.time())),
    }
    await store.set_token(token_hash_value, data, ttl_effective)

    if ttl_effective <= 0:
        logger.warning(
            "token created with no TTL (hosts=%s, email=%s)",
            hosts,
            email or "-",
        )

    return raw_token


async def delete_token(store: TokenStore, token_hash: str) -> None:
    await store.delete_token(token_hash)
    logger.info("token deleted: hash=%s...", token_hash[:12])
