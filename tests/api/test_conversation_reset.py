"""API tests for POST /api/conversations/reset."""

import os
import tempfile
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import create_app
from backend.database.connection import DatabaseManager
from backend.api.dependencies import get_db_manager


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_reset.db")
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
async def test_conversation_reset_clears_only_target_session(temp_db):
    """Test 15: Reset removes messages for specified session without deleting other students' data."""
    db_mgr = DatabaseManager(db_path=temp_db)
    await db_mgr.initialize()

    sess_a = str(uuid.uuid4())
    sess_b = str(uuid.uuid4())

    async with db_mgr.transaction() as conn:
        # Create both sessions
        await conn.execute("INSERT INTO conversations VALUES (?, '2026-11-10', '2026-11-10');", (sess_a,))
        await conn.execute("INSERT INTO conversations VALUES (?, '2026-11-10', '2026-11-10');", (sess_b,))

        # Add messages for both
        await conn.execute("INSERT INTO messages (session_id, role, content, sources_json, created_at) VALUES (?, 'user', 'Question A', '[]', '2026-11-10');", (sess_a,))
        await conn.execute("INSERT INTO messages (session_id, role, content, sources_json, created_at) VALUES (?, 'user', 'Question B', '[]', '2026-11-10');", (sess_b,))

    app = create_app()
    app.dependency_overrides[get_db_manager] = lambda: db_mgr

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Reset session A
        resp = await client.post("/api/conversations/reset", json={"session_id": sess_a})

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == sess_a
    assert data["cleared_messages_count"] == 1

    # Verify session B messages still exist
    async with db_mgr.connection() as conn:
        async with conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?;", (sess_b,)) as cursor:
            count_b = (await cursor.fetchone())[0]
            assert count_b == 1

        async with conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?;", (sess_a,)) as cursor:
            count_a = (await cursor.fetchone())[0]
            assert count_a == 0


@pytest.mark.asyncio
async def test_conversation_reset_invalid_uuid_rejected(temp_db):
    """Verify invalid session ID is rejected with 422."""
    db_mgr = DatabaseManager(db_path=temp_db)
    await db_mgr.initialize()

    app = create_app()
    app.dependency_overrides[get_db_manager] = lambda: db_mgr

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/conversations/reset", json={"session_id": "not-a-uuid"})

    assert resp.status_code == 422
