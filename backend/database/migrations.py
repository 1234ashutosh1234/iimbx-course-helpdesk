"""Versioned, repeatable schema migration runner."""

import aiosqlite
from datetime import datetime, timezone
from backend.database.schema import SCHEMA_V1


MIGRATIONS = [
    (1, "Baseline production schema v1", SCHEMA_V1),
]


async def run_migrations(db: aiosqlite.Connection) -> int:
    """Apply all unapplied schema migrations in sequence.

    Args:
        db: Active aiosqlite database connection.

    Returns:
        int: Number of newly applied migrations.
    """
    # Ensure migrations tracking table exists
    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            description TEXT NOT NULL
        );
    """)
    await db.commit()

    # Determine currently applied version
    async with db.execute("SELECT version FROM schema_migrations;") as cursor:
        rows = await cursor.fetchall()
        applied_versions = {row[0] for row in rows}

    applied_count = 0
    for version, description, ddl in MIGRATIONS:
        if version not in applied_versions:
            # Execute migration DDL inside a transaction
            await db.executescript(ddl)
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?);",
                (version, now_iso, description),
            )
            await db.commit()
            applied_count += 1

    return applied_count
