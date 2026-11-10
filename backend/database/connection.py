"""SQLite connection manager supporting WAL mode, foreign keys, and transactions."""

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import AsyncGenerator, Optional
import aiosqlite

from backend.config import DATABASE_PATH, DATABASE_BUSY_TIMEOUT_MS
from backend.database.migrations import run_migrations


class DatabaseManager:
    """Manages SQLite connection lifecycle, WAL configuration, and migrations."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        busy_timeout_ms: Optional[int] = None,
    ):
        """Initialize database manager.

        Args:
            db_path: Path to SQLite database file or ':memory:'.
            busy_timeout_ms: Milliseconds to wait before busy timeout.
        """
        self.db_path = str(db_path or DATABASE_PATH)
        self.busy_timeout_ms = (
            busy_timeout_ms if busy_timeout_ms is not None else DATABASE_BUSY_TIMEOUT_MS
        )
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize database file, configure pragmas (WAL mode), and run migrations."""
        async with self._init_lock:
            if self._initialized:
                return

            is_memory = self.db_path == ":memory:" or "mode=memory" in self.db_path
            if not is_memory:
                Path(self.db_path).resolve().parent.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as conn:
                # Enable foreign key constraint checks
                await conn.execute("PRAGMA foreign_keys = ON;")
                await conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")
                await conn.execute("PRAGMA synchronous = NORMAL;")

                # WAL mode applies to disk-backed databases
                if not is_memory:
                    await conn.execute("PRAGMA journal_mode = WAL;")

                # Apply versioned migrations
                await run_migrations(conn)

            self._initialized = True

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Provide an active configured SQLite connection.

        Yields:
            aiosqlite.Connection: Active database connection.
        """
        if not self._initialized:
            await self.initialize()

        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")
            await conn.execute("PRAGMA synchronous = NORMAL;")
            yield conn
        finally:
            await conn.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Execute operations within an atomic database transaction.

        Rolls back on unhandled exceptions and commits on successful completion.

        Yields:
            aiosqlite.Connection: Active transaction connection.
        """
        async with self.connection() as conn:
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise


# Default singleton instance using configured environment settings
default_db_manager = DatabaseManager()
