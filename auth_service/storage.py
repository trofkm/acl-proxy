from typing import Protocol


class TokenStore(Protocol):
    async def get_token(self, token_hash: str) -> dict | None:
        """Return token metadata dict or None if not found/expired."""
        ...

    async def set_token(self, token_hash: str, data: dict, ttl: int = 0) -> None:
        """Store token metadata.

        data keys: hosts, email, comment, created_at.
        If ttl > 0, the token expires after ttl seconds.
        """
        ...

    async def delete_token(self, token_hash: str) -> None:
        """Remove token from store."""
        ...

    async def list_tokens(self) -> list[dict]:
        """Return all active tokens.

        Each dict: token_hash, hosts, email, comment, created_at_raw, ttl.
        ttl is -1 for no expiry, >0 for seconds remaining.
        """
        ...

    async def health(self) -> bool:
        """Check if store is reachable. Returns True if healthy."""
        ...
