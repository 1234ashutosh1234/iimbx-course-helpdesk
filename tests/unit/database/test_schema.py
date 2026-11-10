"""Unit tests verifying SQLite tables, indices, and concurrent counter safety."""

import asyncio
import os
import tempfile
import pytest

from backend.database.connection import DatabaseManager


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_schema.db")
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
async def test_all_required_tables_exist(temp_db):
    """Verify all 6 core business tables and migrations tracking table exist."""
    db_mgr = DatabaseManager(db_path=temp_db)
    await db_mgr.initialize()

    expected_tables = {
        "conversations",
        "messages",
        "response_cache",
        "system_metrics",
        "idempotency_keys",
        "inflight_requests",
        "schema_migrations",
    }

    async with db_mgr.connection() as conn:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
        ) as cursor:
            tables = {row[0] for row in await cursor.fetchall()}

    assert expected_tables.issubset(tables)


@pytest.mark.asyncio
async def test_default_telemetry_metrics_initialized(temp_db):
    """Verify system_metrics table is pre-populated with total_questions, gemini_calls, cache_hits at 0."""
    db_mgr = DatabaseManager(db_path=temp_db)
    await db_mgr.initialize()

    async with db_mgr.connection() as conn:
        async with conn.execute("SELECT metric_key, metric_value FROM system_metrics;") as cursor:
            rows = dict(await cursor.fetchall())

    assert rows.get("total_questions") == 0
    assert rows.get("gemini_calls") == 0
    assert rows.get("cache_hits") == 0


@pytest.mark.asyncio
async def test_concurrent_counter_increments_are_not_lost(temp_db):
    """Verify concurrent atomic increments on system_metrics do not lose writes."""
    db_mgr = DatabaseManager(db_path=temp_db)
    await db_mgr.initialize()

    num_concurrent = 25

    async def increment_task():
        async with db_mgr.transaction() as conn:
            await conn.execute(
                """
                UPDATE system_metrics
                SET metric_value = metric_value + 1,
                    updated_at = datetime('now')
                WHERE metric_key = 'total_questions';
                """
            )

    # Run 25 parallel tasks updating total_questions
    await asyncio.gather(*(increment_task() for _ in range(num_concurrent)))

    async with db_mgr.connection() as conn:
        async with conn.execute(
            "SELECT metric_value FROM system_metrics WHERE metric_key = 'total_questions';"
        ) as cursor:
            final_val = (await cursor.fetchone())[0]

    assert final_val == num_concurrent
