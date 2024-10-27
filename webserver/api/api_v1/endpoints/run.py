import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile
from typing import List, Any, Optional, Dict
from pydantic import BaseModel, Field
from assistant import Assistant
from assistant_functions import AssistantFunctions
from webserver.middleware.server_exceptions import BaseHTTPException
from webserver.config import settings

router = APIRouter()
assistant_functions = AssistantFunctions(
    notion_api_key=settings.NOTION_API_KEY,
    notion_running_list_database_id=settings.NOTION_RUNNING_LIST_DATABASE_ID,
    notion_notes_page_id=settings.NOTION_NOTES_PAGE_ID,
    gcal_credentials_path=settings.GCAL_CREDENTIALS_PATH,
    gcal_token_path=settings.GCAL_TOKEN_PATH,
    gcal_auth_method="service_account"
)
ai_assistant = Assistant(api_key=settings.OPENAI_API_KEY, tool_function_map=assistant_functions.get_tool_function_map())

class RequestRun(BaseModel):
    text: Optional[str] = Field(None, title="Text", description="Text based prompt")
    audio: Optional[UploadFile] = Field(None, title="Audio", description="Audio file")
    images: Optional[List[UploadFile]] = Field(None, title="Images", description="Array of image files")
    video: Optional[UploadFile] = Field(None, title="Video", description="Video file")

@router.post("/")
async def post_run(
    request: RequestRun
):
    if all(getattr(request, var, None) is None for var in ["text", "audio", "images", "video"]):
        return { "message": "Missing a valid input." }
    run_result = ai_assistant.perform_run(prompt=request.text)
    run_response = ai_assistant.generate_generic_response(run_result)
    print(run_result)
    return run_response
