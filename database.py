"""Database layer (asyncpg) — same pattern as FactPro."""
import asyncpg
from config import POSTGRES_DSN


class Row(dict):
    pass


def _normalize_dsn(dsn: str) -> str:
    return (
        dsn.replace("postgresql+asyncpg://", "postgresql://")
           .replace("postgres+asyncpg://", "postgresql://")
    )


def _ph(sql: str) -> str:
    i = 0
    out = []
    for ch in sql:
        if ch == "?":
            i += 1
            out.append(f"${i}")
        else:
            out.append(ch)
    return "".join(out)


def _to_pg_ddl(sql: str) -> str:
    return (
        sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
           .replace("CURRENT_TIMESTAMP", "NOW()")
    )


def _prepare(sql: str) -> str:
    return _ph(_to_pg_ddl(sql))


async def get_conn():
    return _PGConn()


class _PGConn:
    async def __aenter__(self):
        self._conn = await asyncpg.connect(_normalize_dsn(POSTGRES_DSN))
        self._tx = self._conn.transaction()
        await self._tx.start()
        return self

    async def __aexit__(self, exc_type, *a):
        try:
            if exc_type:
                await self._tx.rollback()
            else:
                await self._tx.commit()
        finally:
            await self._conn.close()

    async def fetchall(self, sql, params=()):
        rows = await self._conn.fetch(_prepare(sql), *params)
        return [Row(dict(r)) for r in rows]

    async def fetchone(self, sql, params=()):
        r = await self._conn.fetchrow(_prepare(sql), *params)
        return Row(dict(r)) if r else None

    async def execute(self, sql, params=()):
        await self._conn.execute(_prepare(sql), *params)

    async def commit(self):
        await self._tx.commit()
        self._tx = self._conn.transaction()
        await self._tx.start()

    async def lastrowid(self):
        return await self._conn.fetchval("SELECT lastval()")
