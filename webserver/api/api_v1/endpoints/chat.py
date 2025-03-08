import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, status, Depends, Request, File, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from webserver.config import settings
from webserver.db.chatdb.db import mongodb_client
from typing import Optional, List, Dict, Any
from webserver.api.dependencies import verify_access_token, get_session
from webserver.db.chatdb.utils import serialize_doc
from webserver.db.chatdb.models import DBChat, DBChatFile
from webserver.util.s3 import create_chat_s3_storage, get_chat_file_path, create_s3_storage_from_config
import io
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# S3 storage instance for chat file operations - using config-based settings
s3_storage = create_chat_s3_storage()

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
    
    try:
        # First verify the chat belongs to the user
        chat = await mongodb_client.db["chats"].find_one({
            "chat_id": chat_id,
            "user_id": user_id
        })
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        # Get the chat files with their text content
        chat_files = chat.get("files") or []
        file_content_map = {}
        for file in chat_files:
            if "fileid" in file and "text_content" in file:
                file_content_map[file["fileid"]] = {
                    "filename": file.get("filename", "unknown"),
                    "text_content": file["text_content"],
                    "content_type": file.get("content_type", "")
                }
            
        # Get the messages for this chat
        messages = await mongodb_client.db["messages"].find({"chat_id": chat_id}).to_list(length=100)
        
        # Serialize messages and attach file information
        formatted_messages = []
        for message in messages:
            message_dict = serialize_doc(message)
            
            # If the message has file IDs attached, include their content
            if "files" in message_dict and message_dict["files"]:
                file_ids = message_dict["files"]
                message_dict["file_contents"] = {
                    file_id: file_content_map.get(file_id, {}) 
                    for file_id in file_ids 
                    if file_id in file_content_map
                }
                
            formatted_messages.append(message_dict)
            
        return formatted_messages
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")
    except Exception as e:
        logger.error(f"Error getting messages for chat_id {chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")

@router.delete("/{chat_id}", dependencies=[Depends(verify_access_token), Depends(get_session)])
async def delete_chat(chat_id: str, request: Request):
    user_id = request.state.user["user_id"]
    
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
    
    body = await request.json()
    model_id = body.get("model_id")
    model_api_source = body.get("model_api_source")
    if not model_id:
        raise HTTPException(status_code=400, detail="Model ID is required")

    chat = DBChat(
        chat_id=str(uuid.uuid4()),
        user_id=user_id,
        current_model_id=model_id,
        current_model_api_source=model_api_source,
        created_timestamp=datetime.now()
    )

    try:
        await mongodb_client.db["chats"].insert_one(chat.model_dump())
    except Exception as e:
        logger.error(f"Error creating chat {chat.chat_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    return JSONResponse(
        content={"chat_id": chat.chat_id},
        status_code=status.HTTP_200_OK
    )

@router.post("/{chat_id}/upload", 
          dependencies=[Depends(verify_access_token), Depends(get_session)],
          summary="Upload files to a chat",
          response_description="Array of uploaded file metadata")
async def upload_files(
    chat_id: str, 
    request: Request,
    files: List[UploadFile] = File(...)
):
    """
    Upload one or more files to the chat.
    
    Args:
        chat_id: The ID of the chat to upload files to
        files: One or more files to upload
        
    Returns:
        List of file metadata objects
    
    Raises:
        HTTPException: If chat not found or file upload fails
    """
    user_id = request.state.user["user_id"]
    
    # Verify chat exists and belongs to the user
    chat = await mongodb_client.db["chats"].find_one({
        "chat_id": chat_id,
        "user_id": user_id
    })
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    uploaded_files = []
    current_time = datetime.utcnow()
    
    try:
        for upload_file in files:
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            
            # Read file content
            content = await upload_file.read()
            
            # Define S3 object key (path in the bucket)
            object_key = get_chat_file_path(chat_id, file_id, upload_file.filename)
            
            # Upload to S3
            fileobj = io.BytesIO(content)
            success = s3_storage.upload_fileobj(
                fileobj=fileobj,
                object_key=object_key,
                metadata={
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "filename": upload_file.filename,
                    "content_type": upload_file.content_type
                }
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload file {upload_file.filename}"
                )
            
            # Create file metadata
            file_metadata = {
                "fileid": file_id,
                "filename": upload_file.filename,
                "uploaded_at": current_time,
                "userid": user_id,
                "content_type": upload_file.content_type,
                "size": len(content),
                "object_key": object_key,
                "metadata": {}
            }
            
            uploaded_files.append(file_metadata)
        
        # Update chat document with file metadata
        if uploaded_files:
            # Get existing files or initialize an empty array
            existing_files = chat.get("files") or []
            updated_files = existing_files + uploaded_files
            
            # Update MongoDB
            await mongodb_client.db["chats"].update_one(
                {"chat_id": chat_id},
                {"$set": {"files": updated_files}}
            )
        
        return JSONResponse(
            content=serialize_doc(uploaded_files),
            status_code=status.HTTP_200_OK
        )
            
    except Exception as e:
        logger.error(f"Error uploading files to chat {chat_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload files"
        )

@router.get("/{chat_id}/files", 
         dependencies=[Depends(verify_access_token), Depends(get_session)],
         summary="List files in a chat",
         response_description="Array of file metadata")
async def list_files(chat_id: str, request: Request):
    """
    List all files associated with a chat.
    
    Args:
        chat_id: The ID of the chat to list files from
        
    Returns:
        List of file metadata objects
    
    Raises:
        HTTPException: If chat not found
    """
    user_id = request.state.user["user_id"]
    
    # Verify chat exists and belongs to the user
    chat = await mongodb_client.db["chats"].find_one({
        "chat_id": chat_id,
        "user_id": user_id
    })
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Return files from the chat document
    files = chat.get("files", [])
    return JSONResponse(
        content=serialize_doc(files),
        status_code=status.HTTP_200_OK
    )

@router.get("/{chat_id}/files/{file_id}", 
         dependencies=[Depends(verify_access_token), Depends(get_session)],
         summary="Get a file from a chat",
         response_description="File content with appropriate Content-Type")
async def get_file(chat_id: str, file_id: str, request: Request):
    """
    Get a specific file from a chat.
    
    Args:
        chat_id: The ID of the chat
        file_id: The ID of the file to retrieve
        
    Returns:
        StreamingResponse with file content and appropriate content type
    
    Raises:
        HTTPException: If chat or file not found
    """
    user_id = request.state.user["user_id"]
    
    # Verify chat exists and belongs to the user
    chat = await mongodb_client.db["chats"].find_one({
        "chat_id": chat_id,
        "user_id": user_id
    })
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Find the file metadata in the chat document
    files = chat.get("files", [])
    file_metadata = next((f for f in files if f.get("fileid") == file_id), None)
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get the object key from file metadata
    object_key = file_metadata.get("object_key")
    if not object_key:
        object_key = get_chat_file_path(chat_id, file_id, file_metadata.get('filename'))
    
    # Create a BytesIO object to hold the file content
    file_content = io.BytesIO()
    
    # Download the file from S3
    success = s3_storage.download_fileobj(
        object_key=object_key,
        fileobj=file_content
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file from storage"
        )
    
    # Reset the pointer to the beginning of the BytesIO object
    file_content.seek(0)
    
    # Create a streaming response with the file content
    return StreamingResponse(
        content=file_content,
        media_type=file_metadata.get("content_type", "application/octet-stream"),
        headers={
            "Content-Disposition": f"attachment; filename=\"{file_metadata.get('filename')}\""
        }
    )

@router.delete("/{chat_id}/files/{file_id}", 
            dependencies=[Depends(verify_access_token), Depends(get_session)],
            summary="Delete a file from a chat",
            response_description="Deletion status")
async def delete_file(chat_id: str, file_id: str, request: Request):
    """
    Delete a specific file from a chat.
    
    Args:
        chat_id: The ID of the chat
        file_id: The ID of the file to delete
        
    Returns:
        JSON confirmation of deletion
    
    Raises:
        HTTPException: If chat not found or deletion fails
    """
    user_id = request.state.user["user_id"]
    
    # Verify chat exists and belongs to the user
    chat = await mongodb_client.db["chats"].find_one({
        "chat_id": chat_id,
        "user_id": user_id
    })
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Find the file metadata in the chat document
    files = chat.get("files", [])
    file_metadata = next((f for f in files if f.get("fileid") == file_id), None)
    
    # Even if file is not found in metadata, we still try to delete from S3
    # for idempotent behavior
    object_key = None
    if file_metadata:
        object_key = file_metadata.get("object_key")
        if not object_key:
            object_key = get_chat_file_path(chat_id, file_id, file_metadata.get('filename'))
        
        # Try to list and delete all objects with the prefix {chat_id}/{file_id}/
        # This ensures all versions or related files are deleted
        prefix = f"{chat_id}/{file_id}/"
        try:
            all_objects = s3_storage.list_files(prefix=prefix)
            object_keys = [obj["Key"] for obj in all_objects]
            
            if object_keys:
                s3_storage.delete_files(object_keys)
            else:
                # Fallback to specified object key if no objects found with prefix
                s3_storage.delete_file(object_key)
        except Exception as e:
            logger.error(f"Error deleting file {file_id} from S3: {str(e)}", exc_info=True)
            # Continue to database deletion even if S3 deletion fails
    
    # Remove file metadata from the chat document
    if file_metadata:
        try:
            updated_files = [f for f in files if f.get("fileid") != file_id]
            await mongodb_client.db["chats"].update_one(
                {"chat_id": chat_id},
                {"$set": {"files": updated_files}}
            )
        except Exception as e:
            logger.error(f"Error updating chat document after file deletion: {str(e)}", exc_info=True)
            # Continue to return success even if database update fails,
            # as we've already tried to delete the file from S3
    
    # Return success regardless of whether the file existed or not
    # This ensures idempotent behavior
    return JSONResponse(
        content={"message": f"File {file_id} deleted or not found"},
        status_code=status.HTTP_200_OK
    )
