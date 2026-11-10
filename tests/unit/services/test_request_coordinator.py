"""Unit tests for inter-request inflight coordination, leader election, and lease recovery."""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import tempfile
import pytest

from backend.database.connection import DatabaseManager
from backend.services.request_coordinator import RequestCoordinator


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_coordinator.db")
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
def coordinator(temp_db):
    db_mgr = DatabaseManager(db_path=temp_db)
    return RequestCoordinator(db_manager=db_mgr)


@pytest.mark.asyncio
async def test_different_keys_identical_inflight_share_generation(coordinator):
    """Test 23: Two requests for the same fingerprint result in exactly one leader; follower awaits."""
    fingerprint = "fp_passing_criteria_shared"
    worker1 = "worker-1"
    worker2 = "worker-2"

    # Worker 1 acquires leadership
    lead1 = await coordinator.try_acquire_leader(fingerprint, worker1, lease_seconds=10)
    assert lead1 is True

    # Worker 2 attempts concurrently
    lead2 = await coordinator.try_acquire_leader(fingerprint, worker2, lease_seconds=10)
    assert lead2 is False

    # Worker 2 starts awaiting the leader
    await_task = asyncio.create_task(coordinator.await_result(fingerprint, timeout_seconds=5.0))

    # Worker 1 finishes generation and completes
    expected_data = {"answer": "Passing is 60%.", "sources": ["03_grading_policy_v2.txt"]}
    await asyncio.sleep(0.05)
    success = await coordinator.complete_leader(fingerprint, worker1, expected_data)
    assert success is True

    # Worker 2 receives shared result!
    follower_result = await await_task
    assert follower_result == expected_data


@pytest.mark.asyncio
async def test_crashed_or_expired_lease_can_be_recovered(coordinator, temp_db):
    """Test 24: When a leader's lease expires without completion, a new worker can recover leadership."""
    fingerprint = "fp_crashed_worker"
    worker_crashed = "worker-crashed"
    worker_recovery = "worker-recovery"

    # Worker crashed acquires leader with lease of 0 seconds (immediately expired)
    await coordinator.try_acquire_leader(fingerprint, worker_crashed, lease_seconds=0)

    # Let timestamp tick slightly
    await asyncio.sleep(0.05)

    # Recovery worker should successfully acquire leadership
    recovered = await coordinator.try_acquire_leader(fingerprint, worker_recovery, lease_seconds=10)
    assert recovered is True


@pytest.mark.asyncio
async def test_stale_worker_cannot_overwrite_newer_result(coordinator):
    """Test 25: A stale/expired worker whose lease was superseded cannot overwrite completed result."""
    fingerprint = "fp_stale_worker"
    stale_worker = "worker-stale"
    new_leader = "worker-new-leader"

    # Stale worker acquires with 0s lease
    await coordinator.try_acquire_leader(fingerprint, stale_worker, lease_seconds=0)
    await asyncio.sleep(0.05)

    # New leader takes over
    await coordinator.try_acquire_leader(fingerprint, new_leader, lease_seconds=10)

    # New leader completes first
    new_data = {"answer": "New verified answer."}
    completed_by_new = await coordinator.complete_leader(fingerprint, new_leader, new_data)
    assert completed_by_new is True

    # Stale worker tries to overwrite now
    stale_data = {"answer": "Stale outdated answer."}
    overwritten = await coordinator.complete_leader(fingerprint, stale_worker, stale_data)
    assert overwritten is False  # Refused because owner_id does not match!

    # Verify new data remains in place
    result = await coordinator.await_result(fingerprint, timeout_seconds=1.0)
    assert result == new_data
