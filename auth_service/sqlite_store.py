import time

import aiosqlite


class SQLiteTokenStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA wal_autocheckpoint=1000")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("""CREATE TABLE IF NOT EXISTS tokens (
                token_hash TEXT PRIMARY KEY,
                hosts TEXT NOT NULL,
                email TEXT DEFAULT '',
                comment TEXT DEFAULT '',
                created_at INTEGER NOT NULL,
                expires_at INTEGER DEFAULT 0
            )""")
        await self._conn.commit()

    async def get_token(self, token_hash: str) -> dict | None:
        conn = self._conn
        if conn is None:
            return None
        cursor = await conn.execute(
            "SELECT hosts, email, comment, created_at, expires_at FROM tokens "
            "WHERE token_hash = ?",
            (token_hash,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        hosts, email, comment, created_at, expires_at = row
        if expires_at > 0 and expires_at < int(time.time()):
            await conn.execute("DELETE FROM tokens WHERE token_hash = ?", (token_hash,))
            await conn.commit()
            return None

        return {
            "hosts": hosts,
            "email": email,
            "comment": comment,
            "created_at": str(created_at),
        }

    async def set_token(self, token_hash: str, data: dict, ttl: int = 0) -> None:
        conn = self._conn
        if conn is None:
            return
        created_at = int(data.get("created_at", int(time.time())))
        expires_at = int(time.time()) + ttl if ttl > 0 else 0
        await conn.execute(
            """INSERT OR REPLACE INTO tokens
               (token_hash, hosts, email, comment, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                token_hash,
                data.get("hosts", ""),
                data.get("email", ""),
                data.get("comment", ""),
                created_at,
                expires_at,
            ),
        )
        await conn.commit()

    async def delete_token(self, token_hash: str) -> None:
        conn = self._conn
        if conn is None:
            return
        await conn.execute("DELETE FROM tokens WHERE token_hash = ?", (token_hash,))
        await conn.commit()

    async def list_tokens(self) -> list[dict]:
        conn = self._conn
        if conn is None:
            return []
        cursor = await conn.execute(
            "SELECT token_hash, hosts, email, comment, created_at, expires_at "
            "FROM tokens"
        )
        rows = await cursor.fetchall()
        now = int(time.time())
        tokens: list[dict] = []
        expired: list[str] = []
        for row in rows:
            token_hash, hosts, email, comment, created_at, expires_at = row
            if expires_at > 0 and expires_at < now:
                expired.append(token_hash)
                continue
            tokens.append(
                {
                    "token_hash": token_hash,
                    "hosts": hosts,
                    "email": email,
                    "comment": comment,
                    "created_at_raw": str(created_at),
                    "ttl": max(0, expires_at - now) if expires_at > 0 else -1,
                }
            )
        if expired:
            for h in expired:
                await conn.execute("DELETE FROM tokens WHERE token_hash = ?", (h,))
            await conn.commit()
        return tokens

    async def health(self) -> bool:
        try:
            conn = self._conn
            if conn is None:
                return False
            await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
