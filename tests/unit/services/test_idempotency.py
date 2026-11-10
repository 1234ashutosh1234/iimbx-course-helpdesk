"""Unit tests for idempotency key registration, replay, conflict detection, and lease safety."""

import asyncio
import os
import tempfile
import pytest

from backend.database.connection import DatabaseManager
from backend.services.idempotency import (
    IdempotencyService,
    IdempotencyConflictError,
)


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_idempotency.db")
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
def idemp_service(temp_db):
    db_mgr = DatabaseManager(db_path=temp_db)
    return IdempotencyService(db_manager=db_mgr)


@pytest.mark.asyncio
async def test_same_key_and_same_payload_reuses_completed_response(idemp_service):
    """Test 20: Same key and payload returns saved completed response on replay."""
    key = "idem-key-101"
    session_id = "sess-1"
    question = "What is the passing score?"
    req_hash = IdempotencyService.compute_request_hash(session_id, question)

    # 1. First registration: returns 'new'
    status, data = await idemp_service.check_or_register_key(key, session_id, req_hash)
    assert status == "new"
    assert data is None

    # 2. Complete the request with result
    expected_resp = {
        "answer": "Minimum 60% overall and 40% in the final exam.",
        "sources": ["03_grading_policy_v2.txt"],
        "canonical_topic": "PASSING_CRITERIA",
        "is_supported": True,
    }
    await idemp_service.complete_key(key, expected_resp)

    # 3. Second call with same key and payload: returns 'completed' and exact payload
    status2, data2 = await idemp_service.check_or_register_key(key, session_id, req_hash)
    assert status2 == "completed"
    assert data2 == expected_resp


@pytest.mark.asyncio
async def test_same_key_with_different_payload_is_rejected(idemp_service):
    """Test 21: Reusing an idempotency key for a different question raises IdempotencyConflictError."""
    key = "idem-key-conflict"
    session_id = "sess-1"
    hash1 = IdempotencyService.compute_request_hash(session_id, "What is the passing score?")
    hash2 = IdempotencyService.compute_request_hash(session_id, "What is the capstone deadline?")

    # Register first payload
    status, _ = await idemp_service.check_or_register_key(key, session_id, hash1)
    assert status == "new"

    # Send second payload with identical key -> conflict!
    with pytest.raises(IdempotencyConflictError) as exc_info:
        await idemp_service.check_or_register_key(key, session_id, hash2)

    assert "different request payload" in str(exc_info.value)


@pytest.mark.asyncio
async def test_concurrent_same_key_requests_coordinate_cleanly(idemp_service):
    """Test 22: Concurrent same-key requests yield only one 'new' status; second is 'processing'."""
    key = "concurrent-same-key"
    session_id = "sess-2"
    req_hash = IdempotencyService.compute_request_hash(session_id, "Tell me about the exam.")

    async def register_caller():
        return await idemp_service.check_or_register_key(key, session_id, req_hash)

    # Run two calls concurrently
    res1, res2 = await asyncio.gather(register_caller(), register_caller())

    statuses = {res1[0], res2[0]}
    # Exactly one must be 'new' and one must be 'processing'
    assert statuses == {"new", "processing"}


@pytest.mark.asyncio
async def test_failed_requests_do_not_remain_permanently_stuck(idemp_service):
    """Test 26: A failed request marked with fail_key returns status 'failed'."""
    key = "failed-key-test"
    session_id = "sess-fail"
    req_hash = IdempotencyService.compute_request_hash(session_id, "Any question")

    await idemp_service.check_or_register_key(key, session_id, req_hash)
    await idemp_service.fail_key(key)

    status, _ = await idemp_service.check_or_register_key(key, session_id, req_hash)
    assert status == "failed"
