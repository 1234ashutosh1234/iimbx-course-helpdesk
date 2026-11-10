"""Unit tests for SQLite response caching, deterministic key derivation, and invalidation."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
import tempfile
import pytest

from backend.database.connection import DatabaseManager
from backend.services.cache_service import CacheService
from backend.knowledge.schemas import CanonicalTopic
from backend.knowledge.retrieval import RetrievalEngine


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_cache.db")
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
def cache_service(temp_db):
    db_mgr = DatabaseManager(db_path=temp_db)
    return CacheService(db_manager=db_mgr)


@pytest.mark.asyncio
async def test_first_supported_request_is_cache_miss_and_second_is_hit(cache_service):
    """Test 8 & 9: First request is a cache miss; second equivalent request is a cache hit."""
    cache_key = CacheService.build_cache_key(
        intent_id="intent:passing_criteria",
        canonical_topic="PASSING_CRITERIA",
        corpus_version="hash123",
        evidence_digest="digest123",
    )

    # 1. Miss initially
    entry = await cache_service.get_cached_answer(cache_key)
    assert entry is None

    # 2. Save answer
    saved = await cache_service.save_cached_answer(
        cache_key=cache_key,
        canonical_topic="PASSING_CRITERIA",
        intent_id="intent:passing_criteria",
        corpus_version="hash123",
        evidence_digest="digest123",
        response_text="Minimum 60% overall and 40% on the final exam.",
        sources=["03_grading_policy_v2.txt"],
        is_supported=True,
    )
    assert saved is True

    # 3. Hit on second lookup
    entry = await cache_service.get_cached_answer(cache_key)
    assert entry is not None
    assert "60%" in entry.response_text
    assert json.loads(entry.sources_json) == ["03_grading_policy_v2.txt"]


def test_paraphrased_equivalent_questions_share_cache_key():
    """Test 10: Semantically equivalent questions share the identical cache key."""
    retrieval = RetrievalEngine()
    ev1 = retrieval.retrieve("How much do I need to score to pass DPM-101?")
    ev2 = retrieval.retrieve("What is the minimum passing percentage for DPM-101?")

    digest1 = CacheService.compute_evidence_digest(ev1.evidence)
    digest2 = CacheService.compute_evidence_digest(ev2.evidence)

    k1 = CacheService.build_cache_key(
        intent_id=ev1.intent_id,
        canonical_topic=ev1.canonical_topic.value,
        corpus_version=ev1.corpus_version,
        evidence_digest=digest1,
    )
    k2 = CacheService.build_cache_key(
        intent_id=ev2.intent_id,
        canonical_topic=ev2.canonical_topic.value,
        corpus_version=ev2.corpus_version,
        evidence_digest=digest2,
    )

    assert k1 == k2


def test_different_question_scopes_do_not_collide():
    """Test 11: Different policy topics generate completely different cache keys."""
    retrieval = RetrievalEngine()
    ev_pass = retrieval.retrieve("What is the passing score?")
    ev_late = retrieval.retrieve("What is the late submission policy?")

    d_pass = CacheService.compute_evidence_digest(ev_pass.evidence)
    d_late = CacheService.compute_evidence_digest(ev_late.evidence)

    k_pass = CacheService.build_cache_key(
        intent_id=ev_pass.intent_id,
        canonical_topic=ev_pass.canonical_topic.value,
        corpus_version=ev_pass.corpus_version,
        evidence_digest=d_pass,
    )
    k_late = CacheService.build_cache_key(
        intent_id=ev_late.intent_id,
        canonical_topic=ev_late.canonical_topic.value,
        corpus_version=ev_late.corpus_version,
        evidence_digest=d_late,
    )

    assert k_pass != k_late


def test_refund_followup_does_not_reuse_certificate_fee_key():
    """Test 12: A refund follow-up produces a distinct key and never reuses certificate fee."""
    retrieval = RetrievalEngine()
    ev_fee = retrieval.retrieve("How much does the certificate cost?")
    ev_refund_followup = retrieval.retrieve(
        "Can I get a refund?",
        conversation_context=[{"role": "user", "content": "How much does the certificate cost?"}],
    )

    d_fee = CacheService.compute_evidence_digest(ev_fee.evidence)
    d_refund = CacheService.compute_evidence_digest(ev_refund_followup.evidence)

    ctx_refund = CacheService.compute_context_fingerprint(
        [{"role": "user", "content": "How much does the certificate cost?"}]
    )

    k_fee = CacheService.build_cache_key(
        intent_id=ev_fee.intent_id,
        canonical_topic=ev_fee.canonical_topic.value,
        corpus_version=ev_fee.corpus_version,
        evidence_digest=d_fee,
    )
    k_refund = CacheService.build_cache_key(
        intent_id=ev_refund_followup.intent_id,
        canonical_topic=ev_refund_followup.canonical_topic.value,
        corpus_version=ev_refund_followup.corpus_version,
        evidence_digest=d_refund,
        context_fingerprint=ctx_refund,
    )

    assert k_fee != k_refund
    assert ev_refund_followup.canonical_topic == CanonicalTopic.REFUND_POLICY


def test_cache_invalidation_on_corpus_model_or_prompt_change():
    """Test 13, 14, 15: Invalidation when corpus version, model, or prompt version changes."""
    base_key = CacheService.build_cache_key(
        intent_id="intent:capstone_deadline",
        canonical_topic="CAPSTONE_DEADLINE",
        corpus_version="hash_v1",
        evidence_digest="digest_original",
        model_name="gemini-3.8-flash",
        prompt_version="v1.0",
    )

    # 13. Changed corpus version
    corpus_changed_key = CacheService.build_cache_key(
        intent_id="intent:capstone_deadline",
        canonical_topic="CAPSTONE_DEADLINE",
        corpus_version="hash_v2_updated",
        evidence_digest="digest_original",
        model_name="gemini-3.8-flash",
        prompt_version="v1.0",
    )
    assert base_key != corpus_changed_key

    # 14. Changed model version
    model_changed_key = CacheService.build_cache_key(
        intent_id="intent:capstone_deadline",
        canonical_topic="CAPSTONE_DEADLINE",
        corpus_version="hash_v1",
        evidence_digest="digest_original",
        model_name="gemini-3.0-pro",
        prompt_version="v1.0",
    )
    assert base_key != model_changed_key

    # 15. Changed prompt version
    prompt_changed_key = CacheService.build_cache_key(
        intent_id="intent:capstone_deadline",
        canonical_topic="CAPSTONE_DEADLINE",
        corpus_version="hash_v1",
        evidence_digest="digest_original",
        model_name="gemini-3.8-flash",
        prompt_version="v2.0",
    )
    assert base_key != prompt_changed_key


@pytest.mark.asyncio
async def test_expired_entries_are_rejected(cache_service):
    """Test 16: Expired cache entries are not returned by get_cached_answer."""
    cache_key = "test_expired_key"
    # Save with TTL = -10 seconds (already expired)
    await cache_service.save_cached_answer(
        cache_key=cache_key,
        canonical_topic="PASSING_CRITERIA",
        intent_id="intent:passing_criteria",
        corpus_version="hash123",
        evidence_digest="digest123",
        response_text="Passing score is 60%.",
        sources=["03_grading_policy_v2.txt"],
        ttl_seconds=-10,
    )

    entry = await cache_service.get_cached_answer(cache_key)
    assert entry is None

    # Verify cleanup removes it
    purged = await cache_service.cleanup_expired_cache()
    assert purged >= 1


@pytest.mark.asyncio
async def test_failed_or_unsupported_responses_are_never_cached(cache_service):
    """Test 17 & 18: Unsupported or empty/failed answers are rejected by save_cached_answer."""
    # Unsupported answer
    saved_unsupported = await cache_service.save_cached_answer(
        cache_key="unsupported_key",
        canonical_topic="REFUND_POLICY",
        intent_id="intent:refund_policy",
        corpus_version="hash123",
        evidence_digest="digest123",
        response_text="I do not have information regarding refund policy.",
        sources=[],
        is_supported=False,
    )
    assert saved_unsupported is False

    # Empty response
    saved_empty = await cache_service.save_cached_answer(
        cache_key="empty_key",
        canonical_topic="PASSING_CRITERIA",
        intent_id="intent:passing_criteria",
        corpus_version="hash123",
        evidence_digest="digest123",
        response_text="",
        sources=["03_grading_policy_v2.txt"],
        is_supported=True,
    )
    assert saved_empty is False

    # Missing sources
    saved_no_sources = await cache_service.save_cached_answer(
        cache_key="no_sources_key",
        canonical_topic="PASSING_CRITERIA",
        intent_id="intent:passing_criteria",
        corpus_version="hash123",
        evidence_digest="digest123",
        response_text="Passing score is 60%.",
        sources=[],
        is_supported=True,
    )
    assert saved_no_sources is False


@pytest.mark.asyncio
async def test_source_filenames_survive_cache_storage_and_retrieval(cache_service):
    """Test 19: Source filenames survive round-trip storage and JSON parsing intact."""
    sources = ["01_course_handbook.txt", "03_grading_policy_v2.txt"]
    cache_key = "test_sources_survival"

    await cache_service.save_cached_answer(
        cache_key=cache_key,
        canonical_topic="PASSING_CRITERIA",
        intent_id="intent:passing_criteria",
        corpus_version="hash123",
        evidence_digest="digest123",
        response_text="Official grading rules.",
        sources=sources,
        is_supported=True,
    )

    entry = await cache_service.get_cached_answer(cache_key)
    assert entry is not None
    loaded_sources = json.loads(entry.sources_json)
    assert loaded_sources == sources
