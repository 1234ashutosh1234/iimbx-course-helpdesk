"""Conversation management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from backend.api.schemas import ConversationResetRequest, ConversationResetResponse
from backend.api.dependencies import get_db_manager
from backend.database.connection import DatabaseManager

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.post("/reset", response_model=ConversationResetResponse)
async def reset_conversation(
    req: ConversationResetRequest,
    db_manager: DatabaseManager = Depends(get_db_manager),
):
    """Safely reset conversation message history for a specific session.

    Safety:
    - Never deletes or resets other students' sessions.
    - Never touches system telemetry metrics.
    """
    session_id = req.session_id
    try:
        async with db_manager.transaction() as conn:
            # Delete messages belonging exclusively to this session
            cursor = await conn.execute(
                "DELETE FROM messages WHERE session_id = ?;",
                (session_id,),
            )
            deleted_count = cursor.rowcount

            # Update conversation timestamp or recreate conversation row
            await conn.execute(
                """
                UPDATE conversations
                SET updated_at = datetime('now')
                WHERE session_id = ?;
                """,
                (session_id,),
            )

        return ConversationResetResponse(
            session_id=session_id,
            cleared_messages_count=deleted_count,
            message=f"Session {session_id} conversation history cleared successfully.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset conversation history.",
        )
