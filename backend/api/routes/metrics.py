"""Live telemetry metrics endpoint implementation."""

from fastapi import APIRouter, Depends
from backend.api.schemas import MetricsResponseSchema
from backend.api.dependencies import get_metrics_service
from backend.services.metrics_service import MetricsService

router = APIRouter(prefix="/api", tags=["Telemetry"])


@router.get("/metrics", response_model=MetricsResponseSchema)
async def get_system_metrics(
    metrics_service: MetricsService = Depends(get_metrics_service),
):
    """Retrieve live SQLite telemetry metrics for evaluators and frontend counters."""
    metrics = await metrics_service.get_metrics()
    return MetricsResponseSchema(
        total_questions=metrics.get("total_questions", 0),
        gemini_calls=metrics.get("gemini_calls", 0),
        cache_hits=metrics.get("cache_hits", 0),
    )
