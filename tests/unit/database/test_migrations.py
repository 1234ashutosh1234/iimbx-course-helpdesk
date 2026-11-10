"""Unit tests for versioned, repeatable schema migrations."""

import os
import tempfile
import aiosqlite
import pytest

from backend.database.connection import DatabaseManager
from backend.database.migrations import run_migrations


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_migrations.db")
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
async def test_schema_initialization_is_repeatable(temp_db):
    """Verify running migrations multiple times is completely idempotent and safe."""
    db_mgr = DatabaseManager(db_path=temp_db)
    await db_mgr.initialize()

    # Second initialization via run_migrations directly
    async with aiosqlite.connect(temp_db) as conn:
        applied = await run_migrations(conn)
        assert applied == 0  # No new migrations applied

    # Verify migration record
    async with db_mgr.connection() as conn:
        async with conn.execute("SELECT version, description FROM schema_migrations;") as cursor:
            records = await cursor.fetchall()
            assert len(records) == 1
            assert records[0][0] == 1
            assert "Baseline" in records[0][1]
