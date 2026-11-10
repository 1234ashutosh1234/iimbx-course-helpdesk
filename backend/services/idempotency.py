"""Idempotency service enforcing per-request execution guarantees and double-click protection."""

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from backend.config import IDEMPOTENCY_TTL_SECONDS
from backend.database.connection import DatabaseManager, default_db_manager
from backend.database.models import IdempotencyRecord


class IdempotencyError(Exception):
    """Base exception for idempotency issues."""
    pass


class IdempotencyConflictError(IdempotencyError):
    """Raised when an idempotency key is reused with a different request payload."""
    pass


class IdempotencyService:
    """Provides atomic idempotency registration, conflict detection, and response replay."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        default_ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS,
    ):
        """Initialize idempotency service.

        Args:
            db_manager: Optional DatabaseManager instance.
            default_ttl_seconds: Time-to-live for idempotency records.
        """
        self.db = db_manager or default_db_manager
        self.default_ttl = default_ttl_seconds

    @staticmethod
    def compute_request_hash(session_id: str, question: str) -> str:
        """Derive a deterministic SHA-256 fingerprint for a request payload."""
        content = f"{session_id.strip()}|{question.strip()}".encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    async def check_or_register_key(
        self,
        idempotency_key: str,
        session_id: str,
        request_hash: str,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Check or register an idempotency key atomically.

        Args:
            idempotency_key: Unique client-provided token.
            session_id: Student session identifier.
            request_hash: Hash of the request payload.

        Returns:
            Tuple[str, Optional[Dict[str, Any]]]:
                ("new", None) -> First-time valid request; caller proceeds to execute.
                ("completed", data) -> Previously executed; return cached payload immediately.
                ("processing", None) -> Already executing; caller should wait or return in-progress.
                ("failed", None) -> Previous execution failed.

        Raises:
            IdempotencyConflictError: If the same key is sent with different parameters.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_at = (now + timedelta(seconds=self.default_ttl)).isoformat()

        async with self.db.transaction() as conn:
            # Atomic attempt to register key with INSERT OR IGNORE
            cursor = await conn.execute(
                """
                INSERT OR IGNORE INTO idempotency_keys (
                    idempotency_key, session_id, request_hash, status,
                    response_json, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, 'processing', NULL, ?, ?, ?);
                """,
                (idempotency_key, session_id, request_hash, now_iso, now_iso, expires_at),
            )

            if cursor.rowcount > 0:
                # Brand new key registered as 'processing'
                return ("new", None)

            # Key already exists: inspect stored state
            async with conn.execute(
                """
                SELECT idempotency_key, session_id, request_hash, status, response_json, expires_at
                FROM idempotency_keys
                WHERE idempotency_key = ?;
                """,
                (idempotency_key,),
            ) as cursor:
                row = await cursor.fetchone()

                if row is None:
                    return ("failed", None)

                # Existing key found: verify payload consistency
                stored_hash = row["request_hash"]
                if stored_hash != request_hash:
                    raise IdempotencyConflictError(
                        f"Idempotency key '{idempotency_key}' was previously registered with a different request payload."
                    )

                status = row["status"]
                if status == "completed":
                    resp_json = row["response_json"]
                    data = json.loads(resp_json) if resp_json else None
                    return ("completed", data)

                if status == "processing":
                    return ("processing", None)

                return ("failed", None)

    async def wait_for_in_progress(
        self,
        idempotency_key: str,
        timeout_seconds: float = 5.0,
        poll_interval_seconds: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """Wait for a concurrent request with the same idempotency key to complete.

        Args:
            idempotency_key: Key being processed.
            timeout_seconds: Maximum time to wait.
            poll_interval_seconds: Sleep interval between checks.

        Returns:
            Optional[Dict[str, Any]]: Response data if completed within timeout, else None.
        """
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while asyncio.get_running_loop().time() < deadline:
            async with self.db.connection() as conn:
                async with conn.execute(
                    "SELECT status, response_json FROM idempotency_keys WHERE idempotency_key = ?;",
                    (idempotency_key,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        if row["status"] == "completed" and row["response_json"]:
                            return json.loads(row["response_json"])
                        elif row["status"] == "failed":
                            return None

            await asyncio.sleep(poll_interval_seconds)

        return None

    async def complete_key(
        self,
        idempotency_key: str,
        response_data: Dict[str, Any],
    ) -> None:
        """Mark an idempotency key as successfully completed with its response payload."""
        now_iso = datetime.now(timezone.utc).isoformat()
        resp_json = json.dumps(response_data)

        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE idempotency_keys
                SET status = 'completed',
                    response_json = ?,
                    updated_at = ?
                WHERE idempotency_key = ?;
                """,
                (resp_json, now_iso, idempotency_key),
            )

    async def fail_key(self, idempotency_key: str) -> None:
        """Mark an idempotency key as failed so future retries are not indefinitely blocked."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE idempotency_keys
                SET status = 'failed',
                    updated_at = ?
                WHERE idempotency_key = ?;
                """,
                (now_iso, idempotency_key),
            )

    async def cleanup_expired(self) -> int:
        """Purge expired idempotency keys."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM idempotency_keys WHERE expires_at <= ?;",
                (now_iso,),
            )
            return cursor.rowcount
