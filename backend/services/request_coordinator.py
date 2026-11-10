"""Inter-request and inter-process concurrency coordinator for inflight generations."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, Optional
import uuid

from backend.config import INFLIGHT_LEASE_SECONDS
from backend.database.connection import DatabaseManager, default_db_manager


class RequestCoordinator:
    """Coordinates concurrent duplicate requests using SQLite lease locks."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        default_lease_seconds: int = INFLIGHT_LEASE_SECONDS,
    ):
        """Initialize request coordinator.

        Args:
            db_manager: Optional DatabaseManager instance.
            default_lease_seconds: Bounded generation lease in seconds.
        """
        self.db = db_manager or default_db_manager
        self.lease_seconds = default_lease_seconds

    async def try_acquire_leader(
        self,
        fingerprint: str,
        owner_id: str,
        lease_seconds: Optional[int] = None,
    ) -> bool:
        """Attempt to acquire generation leadership for an inflight request.

        Returns True if this worker is granted generation leadership, False if
        another active leader holds the lease or generation is already complete.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        lease = lease_seconds if lease_seconds is not None else self.lease_seconds
        lease_expires_at = (now + timedelta(seconds=lease)).isoformat()

        async with self.db.transaction() as conn:
            # Attempt atomic insert as leader
            cursor = await conn.execute(
                """
                INSERT OR IGNORE INTO inflight_requests (
                    request_fingerprint, owner_id, status, response_json,
                    created_at, updated_at, lease_expires_at
                ) VALUES (?, ?, 'processing', NULL, ?, ?, ?);
                """,
                (fingerprint, owner_id, now_iso, now_iso, lease_expires_at),
            )

            if cursor.rowcount > 0:
                # Successfully inserted: became new leader
                return True

            # Row already exists: check if completed or eligible for lease recovery
            async with conn.execute(
                """
                SELECT owner_id, status, lease_expires_at
                FROM inflight_requests
                WHERE request_fingerprint = ?;
                """,
                (fingerprint,),
            ) as cur:
                row = await cur.fetchone()

            if row is None:
                return False

            status = row["status"]

            # If already completed, not leader
            if status == "completed":
                return False

            # If previous leader failed or timed out, recover leadership
            is_lease_expired = row["lease_expires_at"] <= now_iso
            if status == "failed" or (status == "processing" and is_lease_expired):
                update_cur = await conn.execute(
                    """
                    UPDATE inflight_requests
                    SET owner_id = ?,
                        status = 'processing',
                        updated_at = ?,
                        lease_expires_at = ?
                    WHERE request_fingerprint = ? AND (status = 'failed' OR lease_expires_at <= ?);
                    """,
                    (owner_id, now_iso, lease_expires_at, fingerprint, now_iso),
                )
                return update_cur.rowcount > 0

            # An active leader is currently generating
            return False

    async def complete_leader(
        self,
        fingerprint: str,
        owner_id: str,
        response_data: Dict[str, Any],
    ) -> bool:
        """Mark inflight request as completed with results.

        Safety: Only updates if owner_id still matches, ensuring expired leaders
        cannot overwrite a newer leader's work.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        resp_json = json.dumps(response_data)

        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                """
                UPDATE inflight_requests
                SET status = 'completed',
                    response_json = ?,
                    updated_at = ?
                WHERE request_fingerprint = ? AND owner_id = ?;
                """,
                (resp_json, now_iso, fingerprint, owner_id),
            )
            return cursor.rowcount > 0

    async def fail_leader(self, fingerprint: str, owner_id: str) -> None:
        """Release generation leadership on failure so subsequent callers do not hang."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE inflight_requests
                SET status = 'failed',
                    updated_at = ?
                WHERE request_fingerprint = ? AND owner_id = ?;
                """,
                (now_iso, fingerprint, owner_id),
            )

    async def await_result(
        self,
        fingerprint: str,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """Wait for an active leader's generation result.

        Returns:
            Optional[Dict[str, Any]]: Parsed response if completed successfully, else None.
        """
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while asyncio.get_running_loop().time() < deadline:
            async with self.db.connection() as conn:
                async with conn.execute(
                    """
                    SELECT status, response_json, lease_expires_at
                    FROM inflight_requests
                    WHERE request_fingerprint = ?;
                    """,
                    (fingerprint,),
                ) as cursor:
                    row = await cursor.fetchone()

                    if not row:
                        return None

                    if row["status"] == "completed" and row["response_json"]:
                        return json.loads(row["response_json"])

                    if row["status"] == "failed":
                        return None

                    # If lease expired while waiting, leader crashed
                    now_iso = datetime.now(timezone.utc).isoformat()
                    if row["lease_expires_at"] <= now_iso:
                        return None

            await asyncio.sleep(poll_interval_seconds)

        return None

    async def cleanup_expired(self, max_age_seconds: int = 300) -> int:
        """Remove old finished or abandoned coordination records."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        ).isoformat()
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM inflight_requests WHERE updated_at <= ?;",
                (cutoff,),
            )
            return cursor.rowcount
