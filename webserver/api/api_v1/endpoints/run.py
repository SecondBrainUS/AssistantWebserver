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
from fastapi.responses import StreamingResponse
import base64
import io

router = APIRouter()
assistant_functions = AssistantFunctions(
    openai_api_key=settings.OPENAI_API_KEY,
    notion_api_key=settings.NOTION_API_KEY,
    notion_running_list_database_id=settings.NOTION_RUNNING_LIST_DATABASE_ID,
    notion_notes_page_id=settings.NOTION_NOTES_PAGE_ID,
    gcal_credentials_path=settings.GCAL_CREDENTIALS_PATH,
    gcal_token_path=settings.GCAL_TOKEN_PATH,
    gcal_auth_method="service_account"
)
ai_assistant = Assistant(api_key=settings.OPENAI_API_KEY, tool_function_map=assistant_functions.get_tool_function_map())

# TODO: audio-only response mode with streaming response and no text (new endpoint, run/audio) comparable to run/text, run/all
# TODO: generic endpoint that responds with text and URLs for audio/image/video

@router.post("/")
async def post_run(
    text: Optional[str] = Form(None, description="Text based prompt"),
    audio: Optional[UploadFile] = File(None, description="Audio file"),
    images: Optional[List[UploadFile]] = File(None, description="Array of image files"),
    video: Optional[UploadFile] = File(None, description="Video file")
):
    if all(v is None for v in [text, audio, images, video]):
        return {"message": "Missing a valid input."}

    print(f"Inputs - Text: {text}, Audio: {audio}, Images: {images}, Video: {video}")

    if audio:
        audio_bytes  = await audio.read()
        print(f"Received audio file: {audio.filename}, size: {len(audio_bytes )} bytes")

        # Create an in-memory bytes buffer
        audio_buffer = io.BytesIO(audio_bytes)
        audio_buffer.name = audio.filename  # Set the name attribute

        # Pass the file-like object to the speech_to_text function
        stt_result = ai_assistant.speech_to_text(audio_buffer)

        print(f"STT Result: {stt_result}")

        # Combine speech-to-text result with existing text
        if text:
            text = stt_result + "\n" + text
        else:
            text = stt_result

    run_result = ai_assistant.perform_run(prompt=text)
    run_response_text = ai_assistant.generate_generic_response(run_result)

    run_response = {
        "text": run_response_text,
        "audio": None
    }

    if audio:
        tts_result = ai_assistant.text_to_speech(run_response_text)
        run_response["audio"] = tts_result

    print(run_result)
    return run_response
