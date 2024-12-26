import logging
from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import JSONResponse
from webserver.config import settings
from webserver.db.chatdb.db import mongodb_client
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", 
    summary="Retrieve paginated chats",
    response_description="List of chat documents sorted by creation date")
async def get_chats(
    limit: Optional[int] = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of chats to return (max 100)"
    ),
    offset: Optional[int] = Query(
        default=0,
        ge=0,
        description="Number of chats to skip"
    )
) -> JSONResponse:
    """
    Retrieve paginated chat documents sorted by creation date (newest first).
    
    Args:
        limit: Maximum number of chats to return (default: 20, max: 100)
        offset: Number of chats to skip for pagination (default: 0)
    
    Returns:
        JSONResponse containing:
        - chats: List of chat documents
        - total: Total number of chats in the database
        - has_more: Boolean indicating if more chats are available
    
    Raises:
        HTTPException: If database operation fails
    """
    try:
        # Get total count for pagination info
        total_chats = await mongodb_client.db["chats"].count_documents({})
        
        # Fetch paginated chats
        chats = await mongodb_client.db["chats"].find() \
            .sort("created_at", -1) \
            .skip(offset) \
            .limit(limit) \
            .to_list(length=limit)
        
        return JSONResponse(
            content={
                "chats": chats,
                "total": total_chats,
                "has_more": (offset + len(chats)) < total_chats
            },
            status_code=status.HTTP_200_OK
        )
            
    except Exception as e:
        logger.error("Failed to fetch chats", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch chats from database"
        )


@router.get("/{chat_id}")
async def get_chat(chat_id: str):
    try:
        chat = await mongodb_client.db["chats"].find_one({"chat_id": chat_id})
        return chat
    except Exception as e:
        logger.error(f"Error getting chat for chat_id {chat_id}: {e}", exc_info=True)
        return {"error": e}

@router.get("/{chat_id}/messages")
async def get_messages(chat_id: str):
    try:
        messages = await mongodb_client.db["messages"].find({"chat_id": chat_id}).to_list(length=100)
        return messages
    except Exception as e:
        logger.error(f"Error getting messages for chat_id {chat_id}: {e}", exc_info=True)
        return {"error": e}

