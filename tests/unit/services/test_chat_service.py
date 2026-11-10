"""End-to-end integration and orchestration unit tests for ChatService."""

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock
import pytest

from backend.database.connection import DatabaseManager
from backend.services.chat_service import ChatService
from backend.ai.gemini_client import GeminiClient
from backend.ai.answer_generator import AnswerGenerator
from backend.knowledge.retrieval import RetrievalEngine


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_chat.db")
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
    client = GeminiClient(api_key="mock_key_for_testing")

    async def side_effect(*args, **kwargs):
        # Trigger outbound call hook like real client
        if client.call_hook:
            if asyncio.iscoroutinefunction(client.call_hook):
                await client.call_hook()
            else:
                client.call_hook()
        return json.dumps({
            "answer": "The minimum passing score is 60% overall and 40% on the final proctored exam separately."
        })

    client.generate_content_async = AsyncMock(side_effect=side_effect)
    return client


@pytest.fixture
def chat_service(temp_db, mock_gemini):
    db_mgr = DatabaseManager(db_path=temp_db)
    retrieval = RetrievalEngine()
    answer_gen = AnswerGenerator(retrieval_engine=retrieval, gemini_client=mock_gemini)
    service = ChatService(
        db_manager=db_mgr,
        retrieval_engine=retrieval,
        gemini_client=mock_gemini,
        answer_generator=answer_gen,
    )
    return service


@pytest.mark.asyncio
async def test_supported_question_uses_gemini_then_cache(chat_service, mock_gemini):
    """Test 36, 37, 38: First call uses Gemini, second equivalent call uses cache."""
    # First call: cache miss -> calls Gemini
    resp1 = await chat_service.process_question(
        question="What is the passing score for DPM-101?",
        session_id="session-user-1",
        idempotency_key="key-pass-1",
    )

    assert resp1.is_supported is True
    assert resp1.cache_hit is False
    assert "60%" in resp1.answer
    assert "03_grading_policy_v2.txt" in resp1.sources
    assert resp1.metrics["total_questions"] == 1
    assert resp1.metrics["gemini_calls"] == 1
    assert resp1.metrics["cache_hits"] == 0

    # Second call (different session & key, equivalent question): cache hit -> 0 Gemini calls
    resp2 = await chat_service.process_question(
        question="How much do I need to score to pass DPM-101?",
        session_id="session-user-2",
        idempotency_key="key-pass-2",
    )

    assert resp2.is_supported is True
    assert resp2.cache_hit is True
    assert "60%" in resp2.answer
    assert "03_grading_policy_v2.txt" in resp2.sources
    assert resp2.metrics["total_questions"] == 2
    assert resp2.metrics["gemini_calls"] == 1  # Did NOT increase!
    assert resp2.metrics["cache_hits"] == 1    # Incremented!


@pytest.mark.asyncio
async def test_unsupported_questions_bypass_gemini_completely(chat_service, mock_gemini):
    """Test 39, 40: Unsupported questions (refund, cricket) bypass Gemini and are not cached."""
    # Refund inquiry
    resp_refund = await chat_service.process_question(
        question="Can I get a refund on my certificate payment?",
        session_id="session-refund",
        idempotency_key="key-refund-1",
    )

    assert resp_refund.is_supported is False
    assert resp_refund.cache_hit is False
    assert "not documented" in resp_refund.answer.lower() or "do not have information" in resp_refund.answer.lower()
    assert resp_refund.metrics["total_questions"] == 1
    assert resp_refund.metrics["gemini_calls"] == 0
    assert resp_refund.metrics["cache_hits"] == 0

    # Off-topic inquiry (cricket)
    resp_cricket = await chat_service.process_question(
        question="Who won the cricket match yesterday?",
        session_id="session-cricket",
        idempotency_key="key-cricket-1",
    )

    assert resp_cricket.is_supported is False
    assert resp_cricket.cache_hit is False
    assert resp_cricket.metrics["total_questions"] == 2
    assert resp_cricket.metrics["gemini_calls"] == 0
    assert resp_cricket.metrics["cache_hits"] == 0


@pytest.mark.asyncio
async def test_idempotent_replay_returns_saved_response_without_incrementing(chat_service):
    """Test 45: Replaying the identical idempotency key returns saved response directly."""
    key = "idem-replay-key"
    session_id = "session-replay"
    question = "What is the capstone deadline?"

    resp1 = await chat_service.process_question(
        question=question,
        session_id=session_id,
        idempotency_key=key,
    )
    assert resp1.is_idempotent_replay is False
    assert resp1.metrics["total_questions"] == 1

    # Replay same key and payload
    resp2 = await chat_service.process_question(
        question=question,
        session_id=session_id,
        idempotency_key=key,
    )
    assert resp2.is_idempotent_replay is True
    assert resp2.answer == resp1.answer
    assert resp2.sources == resp1.sources
    assert resp2.metrics["total_questions"] == 1  # Total questions did NOT increment


@pytest.mark.asyncio
async def test_gemini_fallback_saved_when_authoritative(chat_service, mock_gemini):
    """Test 42: When Gemini generation fails, deterministic fallback is returned and saved."""
    # Force Gemini mock to raise exception
    mock_gemini.generate_content_async = AsyncMock(side_effect=RuntimeError("API Failure"))

    resp = await chat_service.process_question(
        question="What is the passing score?",
        session_id="session-fallback",
        idempotency_key="key-fallback-1",
    )

    assert resp.is_supported is True
    assert resp.is_fallback is True
    assert "60%" in resp.answer
    assert "03_grading_policy_v2.txt" in resp.sources


@pytest.mark.asyncio
async def test_context_sensitive_questions_do_not_receive_unrelated_cache(chat_service):
    """Test 44: Contextual follow-up does not collide with or receive unrelated cache answers."""
    # Step 1: User asks certificate fee
    resp_fee = await chat_service.process_question(
        question="How much does the certificate cost?",
        session_id="session-ctx-1",
        idempotency_key="key-ctx-fee",
    )
    assert "1,500" in resp_fee.answer or "1500" in resp_fee.answer

    # Step 2: Contextual follow-up "Can I get a refund for that?"
    context = [{"role": "user", "content": "How much does the certificate cost?"}]
    resp_refund = await chat_service.process_question(
        question="Can I get a refund for that?",
        session_id="session-ctx-1",
        idempotency_key="key-ctx-refund",
        conversation_context=context,
    )

    assert resp_refund.is_supported is False
    assert resp_refund.canonical_topic == "REFUND_POLICY"
    assert "1,500" not in resp_refund.answer  # Did NOT reuse certificate fee!


@pytest.mark.asyncio
async def test_controlled_concurrency_20_requests(chat_service, mock_gemini):
    """Additional Concurrency Requirement: 20 concurrent requests with mocked Gemini.

    Verifies:
    - Exactly 1 outbound Gemini generation for the shared in-flight fingerprint.
    - All 20 requests receive valid grounded responses.
    - 20 unique accepted questions -> total_questions == 20.
    - Coalesced requests do NOT falsely increment cache_hits.
    - No SQLite concurrency violations or database lock errors.
    """
    num_requests = 20
    all_waiting_event = asyncio.Event()
    followers_waiting = 0
    orig_await_result = chat_service.request_coordinator.await_result

    async def tracking_await_result(fingerprint, timeout_seconds=30.0, poll_interval_seconds=0.05):
        nonlocal followers_waiting
        followers_waiting += 1
        if followers_waiting == num_requests - 1:
            all_waiting_event.set()
        return await orig_await_result(fingerprint, timeout_seconds, poll_interval_seconds)

    chat_service.request_coordinator.await_result = tracking_await_result

    async def simulated_gemini(*args, **kwargs):
        # Instrument call hook
        if mock_gemini.call_hook:
            await mock_gemini.call_hook()
        # Deterministically wait until all 19 followers are actively awaiting in-flight resolution
        await asyncio.wait_for(all_waiting_event.wait(), timeout=15.0)
        return json.dumps({
            "answer": "Minimum passing score is 60% overall and 40% on the final proctored exam."
        })

    mock_gemini.generate_content_async = AsyncMock(side_effect=simulated_gemini)

    # Launch 20 concurrent requests simultaneously for the same question
    tasks = [
        chat_service.process_question(
            question="What is the passing score?",
            session_id=f"session-{i}",
            idempotency_key=f"idem-concurrent-{i}",
        )
        for i in range(num_requests)
    ]

    responses = await asyncio.gather(*tasks)

    # 1. All 20 requests succeeded and received grounded answer
    assert len(responses) == num_requests
    for resp in responses:
        assert resp.is_supported is True
        assert "60%" in resp.answer
        assert "03_grading_policy_v2.txt" in resp.sources

    # 2. Check final metrics
    metrics = await chat_service.metrics_service.get_metrics()
    assert metrics["total_questions"] == 20
    assert metrics["gemini_calls"] == 1       # Exactly ONE Gemini call across all 20!
    assert metrics["cache_hits"] == 0        # In-flight coalescing does NOT increment cache_hits!
