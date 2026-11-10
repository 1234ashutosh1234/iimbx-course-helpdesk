"""API integration tests for POST /api/chat."""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import create_app
from backend.database.connection import DatabaseManager
from backend.services.chat_service import ChatService
from backend.ai.gemini_client import GeminiClient
from backend.ai.answer_generator import AnswerGenerator
from backend.knowledge.retrieval import RetrievalEngine
from backend.api.dependencies import get_chat_service, get_db_manager


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_chat_api.db")
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
def mock_gemini():
    client = GeminiClient(api_key="mock_test_key")

    async def mock_generate(*args, **kwargs):
        if client.call_hook:
            if asyncio.iscoroutinefunction(client.call_hook):
                await client.call_hook()
            else:
                client.call_hook()
        return json.dumps({
            "answer": "Minimum passing threshold is 60% overall and 40% on the final exam separately."
        })

    client.generate_content_async = AsyncMock(side_effect=mock_generate)
    return client


@pytest.fixture
def test_app(temp_db, mock_gemini):
    db_mgr = DatabaseManager(db_path=temp_db)
    retrieval = RetrievalEngine()
    answer_gen = AnswerGenerator(retrieval_engine=retrieval, gemini_client=mock_gemini)
    chat_svc = ChatService(
        db_manager=db_mgr,
        retrieval_engine=retrieval,
        gemini_client=mock_gemini,
        answer_generator=answer_gen,
    )

    app = create_app()
    app.dependency_overrides[get_db_manager] = lambda: db_mgr
    app.dependency_overrides[get_chat_service] = lambda: chat_svc
    return app


@pytest.mark.asyncio
async def test_chat_supported_question_flow_and_sources(test_app):
    """Test 3 & 4: Supported question returns 200, grounded answer, and authoritative source filenames."""
    session_id = str(uuid.uuid4())
    key = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.post(
            "/api/chat",
            headers={"X-Idempotency-Key": key},
            json={"session_id": session_id, "message": "What is the passing score for DPM-101?"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_supported"] is True
    assert data["served_from_cache"] is False
    assert "60%" in data["answer"]
    assert "03_grading_policy_v2.txt" in data["sources"]
    assert data["metrics"]["total_questions"] == 1
    assert data["metrics"]["gemini_calls"] == 1
    assert data["metrics"]["cache_hits"] == 0


@pytest.mark.asyncio
async def test_chat_cache_hit_returns_correct_metrics(test_app):
    """Test 6: Second equivalent question hits cache, incrementing cache_hits and bypassing Gemini."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Turn 1
        resp1 = await client.post(
            "/api/chat",
            headers={"X-Idempotency-Key": str(uuid.uuid4())},
            json={"session_id": str(uuid.uuid4()), "message": "What is the passing score?"},
        )
        assert resp1.status_code == 200
        assert resp1.json()["served_from_cache"] is False

        # Turn 2: Equivalent question from different session/key
        resp2 = await client.post(
            "/api/chat",
            headers={"X-Idempotency-Key": str(uuid.uuid4())},
            json={"session_id": str(uuid.uuid4()), "message": "How much do I need to score to pass?"},
        )

    assert resp2.status_code == 200
    data = resp2.json()
    assert data["served_from_cache"] is True
    assert data["metrics"]["total_questions"] == 2
    assert data["metrics"]["gemini_calls"] == 1  # Unchanged!
    assert data["metrics"]["cache_hits"] == 1    # Incremented!


@pytest.mark.asyncio
async def test_chat_unsupported_question_bypasses_gemini(test_app):
    """Test 5: Unsupported refund question returns is_supported: false with 0 Gemini calls."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.post(
            "/api/chat",
            headers={"X-Idempotency-Key": str(uuid.uuid4())},
            json={"session_id": str(uuid.uuid4()), "message": "Can I get a refund for my certificate?"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_supported"] is False
    assert data["served_from_cache"] is False
    assert data["metrics"]["gemini_calls"] == 0


@pytest.mark.asyncio
async def test_chat_idempotency_replay_and_conflict(test_app):
    """Test 7 & 8: Same key and payload returns cached response; same key with different payload returns 409."""
    key = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # First call
        resp1 = await client.post(
            "/api/chat",
            headers={"X-Idempotency-Key": key},
            json={"session_id": session_id, "message": "When is the capstone due?"},
        )
        assert resp1.status_code == 200

        # Duplicate replay with same payload -> 200 with saved response
        resp2 = await client.post(
            "/api/chat",
            headers={"X-Idempotency-Key": key},
            json={"session_id": session_id, "message": "When is the capstone due?"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["answer"] == resp1.json()["answer"]
        assert resp2.json()["metrics"]["total_questions"] == 1  # Not incremented again!

        # Conflict: same key with different message -> 409 Conflict
        resp_conflict = await client.post(
            "/api/chat",
            headers={"X-Idempotency-Key": key},
            json={"session_id": session_id, "message": "Different question entirely"},
        )
        assert resp_conflict.status_code == 409
        assert "conflict" in resp_conflict.json()["error"].lower()


@pytest.mark.asyncio
async def test_chat_input_validation_rules(test_app):
    """Test 9, 10, 11: Validation rejecting invalid UUID, blank input, and excessive length (>1000 chars)."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # 9. Invalid session_id UUID
        resp_uuid = await client.post(
            "/api/chat",
            json={"session_id": "not-a-valid-uuid", "message": "Passing score?"},
        )
        assert resp_uuid.status_code == 422

        # Invalid X-Idempotency-Key UUID
        resp_idem = await client.post(
            "/api/chat",
            headers={"X-Idempotency-Key": "invalid-uuid"},
            json={"session_id": str(uuid.uuid4()), "message": "Passing score?"},
        )
        assert resp_idem.status_code == 422

        # 10. Empty message
        resp_empty = await client.post(
            "/api/chat",
            json={"session_id": str(uuid.uuid4()), "message": "   "},
        )
        assert resp_empty.status_code == 422

        # 11. Excessively long message (> 1000 chars)
        long_text = "A" * 1001
        resp_long = await client.post(
            "/api/chat",
            json={"session_id": str(uuid.uuid4()), "message": long_text},
        )
        assert resp_long.status_code == 422
