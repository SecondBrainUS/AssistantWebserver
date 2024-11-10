import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, Form
from typing import List, Any, Optional, Dict
from pydantic import BaseModel, Field
from assistant import Assistant
from assistant_functions import AssistantFunctions
from webserver.middleware.server_exceptions import BaseHTTPException
from webserver.config import settings
import base64
import io

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
    audio: Optional[str] = Field(None, title="Audio", description="Audio file")
    images: Optional[List[UploadFile]] = Field(None, title="Images", description="Array of image files")
    video: Optional[UploadFile] = Field(None, title="Video", description="Video file")

@router.post("/")
async def post_run(
    request: RequestRun
):
    if all(getattr(request, var, None) is None for var in ["text", "audio", "images", "video"]):
        return {"message": "Missing a valid input."}

    print(f"Request: {request}")

    if request.audio:
        # Decode the Base64 audio data
        audio_data = base64.b64decode(request.audio)
        
        # Convert audio data to a file-like object
        audio_file_like = io.BytesIO(audio_data)

        # Debug: Print the first few bytes to check the format
        audio_file_like.seek(0)
        print(f"First bytes of decoded audio: {audio_file_like.read(16).hex()}")
        audio_file_like.seek(0)
                
        # Pass the file-like object to the speech_to_text function
        stt_result = ai_assistant.speech_to_text(audio_file_like)

        print(f"STT Result: {stt_result}")

        # TODO: if text, append to the beginning of the text
        if request.text:
            request.text = stt_result + "\n" + request.text
        else:
            request.text = stt_result

    run_result = ai_assistant.perform_run(prompt=request.text)
    run_response = ai_assistant.generate_generic_response(run_result)

    print(run_result)
    return run_response
