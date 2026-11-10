"""System health check endpoint implementation."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from backend.api.schemas import HealthResponseSchema
from backend.api.dependencies import get_db_manager
from backend.database.connection import DatabaseManager

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponseSchema)
async def health_check(
    db_manager: DatabaseManager = Depends(get_db_manager),
):
    """Perform non-destructive service health and database availability check.

    Safety: Does not invoke external Gemini APIs or reveal credentials/paths.
    """
    try:
        async with db_manager.connection() as conn:
            async with conn.execute("SELECT 1;") as cursor:
                row = await cursor.fetchone()
                if not row or row[0] != 1:
                    raise RuntimeError("Database query failed.")

        return HealthResponseSchema(
            status="healthy",
            database="connected",
            version="1.0.0",
        )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "database": "unavailable",
                "version": "1.0.0",
            },
        )
