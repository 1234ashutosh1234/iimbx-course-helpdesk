"""Chat endpoint implementation."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from backend.api.schemas import ChatRequest, ChatResponseSchema, ChatMetrics
from backend.api.dependencies import get_chat_service, validate_idempotency_header
from backend.services.chat_service import ChatService
from backend.services.idempotency import IdempotencyConflictError

router = APIRouter(prefix="/api", tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponseSchema,
    responses={
        200: {"description": "Grounded answer successfully generated or retrieved from cache."},
        202: {"description": "Request currently in progress by another worker."},
        409: {"description": "Idempotency key reused with different request payload."},
        422: {"description": "Malformed request or invalid UUID."},
        500: {"description": "Server or model failure."},
    },
)
async def chat_endpoint(
    req: ChatRequest,
    idempotency_key: str = Depends(validate_idempotency_header),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Process a student inquiry through deterministic policy retrieval and AI generation."""
    try:
        # Load conversation history for contextual follow-ups
        history = await chat_service.get_conversation_history(req.session_id, limit=6)

        resp = await chat_service.process_question(
            question=req.message,
            session_id=req.session_id,
            idempotency_key=idempotency_key,
            conversation_context=history,
        )

        if resp.canonical_topic == "IN_PROGRESS":
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                headers={"Retry-After": "1"},
                content={
                    "answer": resp.answer,
                    "sources": [],
                    "is_supported": False,
                    "served_from_cache": False,
                    "session_id": req.session_id,
                    "metrics": resp.metrics or {
                        "total_questions": 0,
                        "gemini_calls": 0,
                        "cache_hits": 0,
                    },
                },
            )

        metrics_dict = resp.metrics or {
            "total_questions": 0,
            "gemini_calls": 0,
            "cache_hits": 0,
        }

        return ChatResponseSchema(
            answer=resp.answer,
            sources=resp.sources,
            is_supported=resp.is_supported,
            served_from_cache=resp.cache_hit,
            session_id=req.session_id,
            metrics=ChatMetrics(
                total_questions=metrics_dict.get("total_questions", 0),
                gemini_calls=metrics_dict.get("gemini_calls", 0),
                cache_hits=metrics_dict.get("cache_hits", 0),
            ),
        )

    except IdempotencyConflictError as ice:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ice),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating your course assistance response. Please try again.",
        )
