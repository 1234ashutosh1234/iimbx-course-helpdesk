"""API tests for GET /api/metrics."""

import os
import tempfile
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import create_app
from backend.database.connection import DatabaseManager
from backend.services.metrics_service import MetricsService
from backend.api.dependencies import get_metrics_service


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_metrics_api.db")
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
async def test_metrics_endpoint_reflects_database_state(temp_db):
    """Test 12: GET /api/metrics reads real counts from SQLite system_metrics."""
    db_mgr = DatabaseManager(db_path=temp_db)
    await db_mgr.initialize()

    metrics_svc = MetricsService(db_manager=db_mgr)
    await metrics_svc.initialize_metrics()

    # Pre-populate metrics
    await metrics_svc.increment_total_questions(5)
    await metrics_svc.increment_gemini_calls(3)
    await metrics_svc.increment_cache_hits(2)

    app = create_app()
    app.dependency_overrides[get_metrics_service] = lambda: metrics_svc

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/metrics")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_questions"] == 5
    assert data["gemini_calls"] == 3
    assert data["cache_hits"] == 2
