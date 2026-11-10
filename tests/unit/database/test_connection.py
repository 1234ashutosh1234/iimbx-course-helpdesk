"""Unit tests for SQLite connection manager, WAL mode, foreign keys, and transactions."""

import asyncio
import os
import tempfile
import aiosqlite
import pytest

from backend.database.connection import DatabaseManager


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path and clean it up after test."""
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_iimbx.db")
    yield db_file
    for ext in ["", "-wal", "-shm"]:
        target = db_file + ext
        if os.path.exists(target):
            try:
                os.remove(target)
            except OSError:
                pass
    if os.path.exists(temp_dir):
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_database_initializes_correctly(temp_db_path):
    """Verify database initializes file and applies schema migrations."""
    db_mgr = DatabaseManager(db_path=temp_db_path)
    await db_mgr.initialize()

    assert os.path.exists(temp_db_path)
    assert db_mgr._initialized is True


@pytest.mark.asyncio
async def test_wal_mode_enabled_on_disk(temp_db_path):
    """Verify WAL journal mode and synchronous NORMAL are active on disk-backed database."""
    db_mgr = DatabaseManager(db_path=temp_db_path)
    await db_mgr.initialize()

    async with db_mgr.connection() as conn:
        async with conn.execute("PRAGMA journal_mode;") as cursor:
            row = await cursor.fetchone()
            assert row[0].lower() == "wal"

        async with conn.execute("PRAGMA synchronous;") as cursor:
            row = await cursor.fetchone()
            # 1 corresponds to NORMAL in SQLite
            assert row[0] in (1, "1", "NORMAL", "normal")


@pytest.mark.asyncio
async def test_foreign_keys_enforced(temp_db_path):
    """Verify foreign key constraint check raises IntegrityError on orphan message insertion."""
    db_mgr = DatabaseManager(db_path=temp_db_path)
    await db_mgr.initialize()

    async with db_mgr.connection() as conn:
        async with conn.execute("PRAGMA foreign_keys;") as cursor:
            row = await cursor.fetchone()
            assert row[0] == 1

        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                """
                INSERT INTO messages (session_id, role, content, sources_json, created_at)
                VALUES ('nonexistent-session', 'user', 'hello', '[]', datetime('now'));
                """
            )
            await conn.commit()


@pytest.mark.asyncio
async def test_transaction_rollback_on_exception(temp_db_path):
    """Verify transaction manager executes rollback when an exception occurs."""
    db_mgr = DatabaseManager(db_path=temp_db_path)
    await db_mgr.initialize()

    # Create parent conversation
    async with db_mgr.transaction() as conn:
        await conn.execute(
            "INSERT INTO conversations (session_id, created_at, updated_at) VALUES ('sess-1', '2026-11-10', '2026-11-10');"
        )

    # Attempt transaction that inserts then raises exception
    with pytest.raises(RuntimeError):
        async with db_mgr.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO messages (session_id, role, content, sources_json, created_at)
                VALUES ('sess-1', 'user', 'This should roll back', '[]', '2026-11-10');
                """
            )
            raise RuntimeError("Forced simulation error")

    # Verify message was NOT saved
    async with db_mgr.connection() as conn:
        async with conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = 'sess-1';") as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 0
