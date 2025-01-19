import logging
import uuid
from datetime import datetime
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
    user_id = ensure_uuid(user_id)
    
    try:
        # Get total count for pagination info
        total_chats = await mongodb_client.db["chats"].count_documents({"user_id": user_id})
        
        # Fetch paginated chats for this user
        chats = await mongodb_client.db["chats"].find({"user_id": user_id}) \
            .sort("created_timestamp", -1) \
            .skip(offset) \
            .limit(limit) \
            .to_list(length=limit)
        
        # Serialize the response
        serialized_chats = serialize_doc(chats)
        
        return JSONResponse(
            content={
                "chats": serialized_chats,
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
    user_id = ensure_uuid(user_id)
    chat_id = ensure_uuid(chat_id)
    
    try:
        chat = await mongodb_client.db["chats"].find_one({
            "chat_id": chat_id,
            "user_id": user_id
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
    user_id = ensure_uuid(user_id)  # Convert to string UUID
    chat_id = ensure_uuid(chat_id)  # Convert to string UUID
    
    try:
        # First verify the chat belongs to the user
        chat = await mongodb_client.db["chats"].find_one({
            "chat_id": chat_id,
            "user_id": user_id
        })
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        messages = await mongodb_client.db["messages"].find({"chat_id": chat_id}).to_list(length=100)
        return serialize_doc(messages)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")
    except Exception as e:
        logger.error(f"Error getting messages for chat_id {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{chat_id}", dependencies=[Depends(verify_access_token), Depends(get_session)])
async def delete_chat(chat_id: str, request: Request):
    user_id = request.state.user["user_id"]
    user_id = ensure_uuid(user_id)  # Convert to string UUID
    chat_id = ensure_uuid(chat_id)  # Convert to string UUID
    
    try:
        # First verify the chat belongs to the user
        chat = await mongodb_client.db["chats"].find_one({
            "chat_id": chat_id,
            "user_id": user_id
        })
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        # Delete messages first
        await mongodb_client.db["messages"].delete_many({"chat_id": chat_id})
        
        # Then delete the chat
        result = await mongodb_client.db["chats"].delete_one({
            "chat_id": chat_id,
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        return JSONResponse(
            content={"message": "Chat deleted successfully"},
            status_code=status.HTTP_200_OK
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")
    except Exception as e:
        logger.error(f"Error deleting chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("", dependencies=[Depends(verify_access_token), Depends(get_session)])
async def create_chat(request: Request):
    user_id = request.state.user["user_id"]
    user_id = ensure_uuid(user_id)
    
    body = await request.json()
    model_id = body.get("model_id")
    if not model_id:
        raise HTTPException(status_code=400, detail="Model ID is required")

    chat_id = str(uuid.uuid4())
    chat_id = uuid_to_binary(chat_id)
    created_timestamp = datetime.now()
    try:
        chat = await mongodb_client.db["chats"].insert_one({
            "chat_id": chat_id,
            "user_id": user_id,
            "current_model_id": model_id,
            "created_timestamp": created_timestamp
        })
    except Exception as e:
        logger.error(f"Error creating chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    return JSONResponse(
        content={"chat_id": chat_id},
        status_code=status.HTTP_200_OK
    )
