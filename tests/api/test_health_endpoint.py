"""API tests for GET /api/health."""

import os
import tempfile
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import create_app
from backend.database.connection import DatabaseManager
from backend.api.dependencies import get_db_manager


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_health.db")
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
async def test_health_check_healthy(temp_db):
    """Test 14: Health check returns 200 and 'healthy' without calling Gemini."""
    db_mgr = DatabaseManager(db_path=temp_db)
    await db_mgr.initialize()

    app = create_app()
    app.dependency_overrides[get_db_manager] = lambda: db_mgr

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data
    # Ensure no internal paths or sensitive details leaked
    assert "path" not in str(data).lower()
    assert "gemini" not in str(data).lower()


@pytest.mark.asyncio
async def test_health_check_database_failure():
    """Test 13: Health check handles database failure gracefully returning 503."""
    class BrokenDBManager:
        def connection(self):
            raise RuntimeError("Simulated database connection failure")

    app = create_app()
    app.dependency_overrides[get_db_manager] = lambda: BrokenDBManager()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")

    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["database"] == "unavailable"
    assert data["database"] == "unavailable"
