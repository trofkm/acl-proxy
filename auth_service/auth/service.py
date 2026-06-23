import hashlib
import hmac

from log import logger
from storage import TokenStore
from validators import host_matches, parse_allowed_hosts


class InvalidTokenError(Exception):
    pass


class ForbiddenHostError(Exception):
    pass


def hash_token(raw_token: str, pepper: str) -> str:
    digest = hmac.new(
        pepper.encode("utf-8"), raw_token.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return digest


async def validate_token(
    store: TokenStore, raw_token: str, host: str, pepper: str
) -> None:
    token_hash = hash_token(raw_token, pepper)
    token_data = await store.get_token(token_hash)

    if not token_data:
        logger.warning("auth: invalid token, host=%s", host)
        raise InvalidTokenError()

    allowed_hosts = parse_allowed_hosts(token_data.get("hosts", ""))

    if not allowed_hosts:
        logger.warning("auth: token has no hosts, token_hash=%s...", token_hash[:12])
        raise ForbiddenHostError()

    requested_host = host.lower()
    matched = any(host_matches(requested_host, pattern) for pattern in allowed_hosts)
    if not matched:
        logger.warning(
            "auth: forbidden, host=%s not in allowed=%s, token_hash=%s...",
            requested_host,
            allowed_hosts,
            token_hash[:12],
        )
        raise ForbiddenHostError()
