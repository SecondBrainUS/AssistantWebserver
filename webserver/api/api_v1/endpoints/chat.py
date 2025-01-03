import logging
from fastapi import APIRouter, Query, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from webserver.config import settings
from webserver.db.chatdb.db import mongodb_client
from typing import Optional
from webserver.api.dependencies import verify_access_token, get_session
from webserver.db.chatdb.utils import serialize_doc
from webserver.db.chatdb.uuid_utils import uuid_to_binary, ensure_uuid

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("", 
    summary="Retrieve paginated chats",
    response_description="List of chat documents sorted by creation date",
    dependencies=[Depends(verify_access_token), Depends(get_session)])
async def get_chats(
    request: Request,
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

    user_id = request.state.user["user_id"]
    user_id_binary = uuid_to_binary(user_id)
    try:
        # Get total count for pagination info
        total_chats = await mongodb_client.db["chats"].count_documents({"user_id": user_id_binary})
        
        # Fetch paginated chats for this user
        chats = await mongodb_client.db["chats"].find({"user_id": user_id_binary}) \
            .sort("created_at", -1) \
            .skip(offset) \
            .limit(limit) \
            .to_list(length=limit)
        
        return JSONResponse(
            content={
                "chats": serialize_doc(chats),
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

@router.get("/{chat_id}", dependencies=[Depends(verify_access_token), Depends(get_session)])
async def get_chat(chat_id: str, request: Request):
    user_id = request.state.user["user_id"]
    try:
        # Convert chat_id to Binary for query
        chat_id_binary = uuid_to_binary(chat_id)
        user_id_binary = uuid_to_binary(user_id)
        chat = await mongodb_client.db["chats"].find_one({
            "chat_id": chat_id_binary,
            "user_id": user_id_binary
        })
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return serialize_doc(chat)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")
    except Exception as e:
        logger.error(f"Error getting chat for chat_id {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{chat_id}/messages", dependencies=[Depends(verify_access_token), Depends(get_session)])
async def get_messages(chat_id: str, request: Request):
    user_id = request.state.user["user_id"]
    try:
        # Convert chat_id to Binary for queries
        chat_id_binary = uuid_to_binary(chat_id)
        user_id_binary = uuid_to_binary(user_id)
        
        # First verify the chat belongs to the user
        chat = await mongodb_client.db["chats"].find_one({
            "chat_id": chat_id_binary,
            "user_id": user_id_binary
        })
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        messages = await mongodb_client.db["messages"].find({"chat_id": chat_id_binary}).to_list(length=100)
        return serialize_doc(messages)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")
    except Exception as e:
        logger.error(f"Error getting messages for chat_id {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
