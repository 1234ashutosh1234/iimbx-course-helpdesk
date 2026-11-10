"""Atomic SQLite telemetry metrics service."""

from datetime import datetime, timezone
from typing import Dict, Optional
from backend.database.connection import DatabaseManager, default_db_manager


class MetricsService:
    """Manages atomic system counters for questions, Gemini API calls, and cache hits."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize metrics service.

        Args:
            db_manager: Optional DatabaseManager instance.
        """
        self.db = db_manager or default_db_manager

    async def initialize_metrics(self) -> None:
        """Ensure all required metric rows exist in system_metrics."""
        now_iso = datetime.now(timezone.utc).isoformat()
        keys = ["total_questions", "gemini_calls", "cache_hits"]
        async with self.db.transaction() as conn:
            for key in keys:
                await conn.execute(
                    """
                    INSERT INTO system_metrics (metric_key, metric_value, updated_at)
                    VALUES (?, 0, ?)
                    ON CONFLICT(metric_key) DO NOTHING;
                    """,
                    (key, now_iso),
                )

    async def increment_total_questions(self, amount: int = 1) -> None:
        """Atomically increment the total_questions counter.

        Rule: Incremented once per accepted unique logical student request.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE system_metrics
                SET metric_value = metric_value + ?,
                    updated_at = ?
                WHERE metric_key = 'total_questions';
                """,
                (amount, now_iso),
            )

    async def increment_gemini_calls(self, amount: int = 1) -> None:
        """Atomically increment the gemini_calls counter.

        Rule: Incremented for every actual outbound Gemini generation attempt (including retries).
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE system_metrics
                SET metric_value = metric_value + ?,
                    updated_at = ?
                WHERE metric_key = 'gemini_calls';
                """,
                (amount, now_iso),
            )

    async def increment_cache_hits(self, amount: int = 1) -> None:
        """Atomically increment the cache_hits counter.

        Rule: Incremented only when a valid persistent response_cache entry supplies the answer.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE system_metrics
                SET metric_value = metric_value + ?,
                    updated_at = ?
                WHERE metric_key = 'cache_hits';
                """,
                (amount, now_iso),
            )

    async def get_metrics(self) -> Dict[str, int]:
        """Fetch current telemetry metrics snapshot.

        Returns:
            Dict[str, int]: Dictionary containing total_questions, gemini_calls, cache_hits.
        """
        metrics = {
            "total_questions": 0,
            "gemini_calls": 0,
            "cache_hits": 0,
        }
        async with self.db.connection() as conn:
            async with conn.execute(
                "SELECT metric_key, metric_value FROM system_metrics;"
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    key = row["metric_key"]
                    if key in metrics:
                        metrics[key] = int(row["metric_value"])

        return metrics
