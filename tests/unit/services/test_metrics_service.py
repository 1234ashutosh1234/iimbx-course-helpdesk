"""Unit tests for atomic telemetry counters, retry tracking, and invariant enforcement."""

import asyncio
import os
import tempfile
import pytest

from backend.database.connection import DatabaseManager
from backend.services.metrics_service import MetricsService


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_metrics.db")
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


@pytest.fixture
def metrics_service(temp_db):
    db_mgr = DatabaseManager(db_path=temp_db)
    return MetricsService(db_manager=db_mgr)


@pytest.mark.asyncio
async def test_initial_metrics_snapshot_all_zero(metrics_service):
    """Verify initial metrics counters all read 0."""
    metrics = await metrics_service.get_metrics()
    assert metrics == {
        "total_questions": 0,
        "gemini_calls": 0,
        "cache_hits": 0,
    }


@pytest.mark.asyncio
async def test_atomic_increments_for_each_counter(metrics_service):
    """Test 27, 29, 31: Verify atomic single increments for questions, API calls, and cache hits."""
    await metrics_service.increment_total_questions()
    await metrics_service.increment_gemini_calls()
    await metrics_service.increment_gemini_calls()  # Second call (e.g., retry)
    await metrics_service.increment_cache_hits()

    metrics = await metrics_service.get_metrics()
    assert metrics["total_questions"] == 1
    assert metrics["gemini_calls"] == 2
    assert metrics["cache_hits"] == 1


@pytest.mark.asyncio
async def test_concurrent_metric_increments_remain_consistent(metrics_service):
    """Test 35: High concurrency increments on counters maintain perfect mathematical integrity."""
    num_updates = 30

    async def update_all():
        await metrics_service.increment_total_questions(1)
        await metrics_service.increment_gemini_calls(1)
        await metrics_service.increment_cache_hits(1)

    await asyncio.gather(*(update_all() for _ in range(num_updates)))

    metrics = await metrics_service.get_metrics()
    assert metrics["total_questions"] == num_updates
    assert metrics["gemini_calls"] == num_updates
    assert metrics["cache_hits"] == num_updates
