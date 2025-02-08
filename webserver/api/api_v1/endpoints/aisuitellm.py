import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from webserver.config import settings
from webserver.ai.aw_aisuite import AiSuiteAssistant
from assistant.assistant_functions import AssistantFunctions

router = APIRouter()
logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role (e.g., 'user', 'assistant', 'system')")
    content: str = Field(..., description="Message content")
    name: Optional[str] = Field(None, description="Optional name for the message sender")

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="List of conversation messages")
    model: str = Field("anthropic:claude-3-sonnet", description="Model identifier")
    temperature: float = Field(0.7, description="Sampling temperature", ge=0.0, le=1.0)

def initialize_ai_suite() -> AiSuiteAssistant:
    """Initialize AISuite with configuration and tools."""
    try:
        # Initialize AI Suite with provider configurations
        config = {}
        
        # Only add credentials that exist and are not None
        if settings.OPENAI_API_KEY:
            config["openai"] = {"api_key": settings.OPENAI_API_KEY}
            
        if settings.ANTHROPIC_API_KEY:
            config["anthropic"] = {"api_key": settings.ANTHROPIC_API_KEY}
            
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            config["aws"] = {
                "access_key_id": settings.AWS_ACCESS_KEY_ID,
                "secret_access_key": settings.AWS_SECRET_ACCESS_KEY
            }
    
        if settings.GROQ_API_KEY:
            config["groq"] = {"api_key": settings.GROQ_API_KEY}
        
        ai_suite = AiSuiteAssistant(config=config)
        
        # Initialize and register assistant functions
        assistant_functions = AssistantFunctions(
            openai_api_key=settings.OPENAI_API_KEY,
            notion_api_key=settings.NOTION_API_KEY,
            notion_running_list_database_id=settings.NOTION_RUNNING_LIST_DATABASE_ID,
            notion_notes_page_id=settings.NOTION_NOTES_PAGE_ID,
            gcal_credentials_path=settings.GCAL_CREDENTIALS_PATH,
            gcal_token_path=settings.GCAL_TOKEN_PATH,
            gcal_auth_method="service_account",
            sensor_values_host=settings.SENSOR_VALUES_HOST_CRITTENDEN,
            sensor_values_metrics=settings.SENSOR_VALUES_METRICS,
            sensor_values_group_id=settings.SENSOR_VALUES_CRITTENDEN_GROUP_ID
        )
        
        # Set tool configuration
        ai_suite.set_tool_function_map(assistant_functions.get_tool_function_map())
        ai_suite.set_tool_chain_config(allow_chaining=True, max_turns=8)
        
        return ai_suite
        
    except Exception as e:
        logger.error(f"Initialization error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI Suite initialization failed")

@router.post("/chat")
async def chat_completion(request: ChatRequest):
    """
    Generate a chat completion response using the configured AI model.
    
    Args:
        request: ChatRequest containing messages and model configuration
    
    Returns:
        JSON response containing the generated content and any tool interactions
    """
    try:
        ai_suite = initialize_ai_suite()
        
        # Convert Pydantic messages to dict format
        messages = [msg.model_dump(exclude_none=True) for msg in request.messages]
        
        # Generate response
        response = await ai_suite.generate_response(
            messages=messages,
            model=request.model,
            temperature=request.temperature
        )
        
        return {
            "id": response.id,
            "content": response.content,
            "tool_calls": [
                {
                    "id": tool_call.call_id,
                    "name": tool_call.name,
                    "arguments": tool_call.arguments
                }
                for tool_call in response.tool_calls
            ],
            "tool_results": [
                {
                    "id": result.call_id,
                    "name": result.name,
                    "result": result.result,
                }
                for result in response.tool_results
            ],
            "token_usage": response.token_usage,
            "stop_reason": response.stop_reason
        }
        
    except Exception as e:
        logger.error(f"Processing error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
