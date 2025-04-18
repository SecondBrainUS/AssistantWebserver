from datetime import datetime
from typing import Literal, Optional, Any, Dict, List
from pydantic import BaseModel

class DBChatFile(BaseModel):
    """Model for file metadata stored in a chat."""
    fileid: str
    filename: str
    uploaded_at: datetime
    userid: str
    content_type: Optional[str] = None
    size: Optional[int] = None
    object_key: Optional[str] = None
    metadata: Dict[str, Any] = {}

class DBChat(BaseModel):
    chat_id: str
    user_id: str
    current_model_api_source: str
    current_model_id: str
    created_timestamp: datetime
    files: Optional[List[Dict[str, Any]]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DBMessageBase(BaseModel):
    message_id: str
    chat_id: str
    model_id: str
    model_api_source: str
    created_timestamp: datetime
    role: Literal["user", "assistant", "system"]
    type: Literal["message", "function_call", "function_result"]

    model_config = {
        'protected_namespaces': (),
        'json_encoders': {
            datetime: lambda v: v.isoformat()
        }
    }

class DBMessageText(DBMessageBase):
    content: str
    modality: Literal["text", "audio"]
    files: Optional[List[str]] = None

class DBMessageAssistantText(DBMessageText):
    usage: Optional[Dict[str, Any]] = None

class DBMessageFunctionCall(DBMessageBase):
    name: str
    arguments: str
    call_id: str

class DBMessageFunctionResult(DBMessageBase):
    name: str
    arguments: str
    call_id: str
    result: Any