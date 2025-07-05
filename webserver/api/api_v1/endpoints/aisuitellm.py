import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from webserver.config import settings
from webserver.ai.aw_aisuite import AiSuiteAssistant
from webserver.api.dependencies import verify_access_token, get_session
from webserver.tools.stocks import get_tool_function_map as get_stocks_tool_map
from webserver.tools.perplexity import get_tool_function_map as get_perplexity_tool_map
from webserver.tools.spotify import get_tool_function_map as get_spotify_tool_map
from webserver.tools.tidal import get_tool_function_map as get_tidal_tool_map
from webserver.tools.notion import get_tool_function_map as get_notion_tool_map
from webserver.tools.google_calendar_helper import get_tool_function_map as get_gcal_tool_map
from webserver.tools.sensor_values import get_tool_function_map as get_sensor_tool_map
from webserver.tools.finance import get_tool_function_map as get_finance_tool_map
from webserver.tools.brightdata_search_tool import get_tool_function_map as get_brightdata_tool_map
from webserver.api.dependencies import verify_access_token, get_session, verify_server_token

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
                
        if settings.GROQ_API_KEY:
            config["groq"] = {"api_key": settings.GROQ_API_KEY}
            
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            config["aws"] = {
                "access_key_id": settings.AWS_ACCESS_KEY_ID,
                "secret_access_key": settings.AWS_SECRET_ACCESS_KEY
            }
        
        ai_suite = AiSuiteAssistant(config=config)
        
        # Get tool maps from all sources
        stocks_tool_map = get_stocks_tool_map()
        finance_tool_map = get_finance_tool_map()
        perplexity_tool_map = get_perplexity_tool_map()
        spotify_tool_map = get_spotify_tool_map()
        tidal_tool_map = get_tidal_tool_map()
        notion_tool_map = get_notion_tool_map()
        gcal_tool_map = get_gcal_tool_map()
        sensor_tool_map = get_sensor_tool_map()
        brightdata_tool_map = get_brightdata_tool_map()
        
        # Merge all tool maps
        tool_map = {
            **stocks_tool_map,
            **finance_tool_map,
            **perplexity_tool_map,
            **spotify_tool_map,
            **tidal_tool_map,
            **notion_tool_map,
            **gcal_tool_map,
            **sensor_tool_map,
            **brightdata_tool_map
        }
        
        # Set tool configuration
        ai_suite.set_tool_function_map(tool_map)
        ai_suite.set_tool_chain_config(allow_chaining=True, max_turns=8)
        
        return ai_suite
        
    except Exception as e:
        logger.error(f"Initialization error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI Suite initialization failed")

@router.post("/chat", dependencies=[Depends(verify_access_token), Depends(get_session)])
async def chat_completion(
    request: Request,
    chat_request: ChatRequest
):
    """
    Generate a chat completion response using the configured AI model.
    
    Args:
        request: FastAPI Request object for accessing user information
        chat_request: ChatRequest containing messages and model configuration
    
    Returns:
        JSON response containing the generated content and any tool interactions
    """
    try:
        ai_suite = initialize_ai_suite()
        
        # Convert Pydantic messages to dict format
        messages = [msg.model_dump(exclude_none=True) for msg in chat_request.messages]
        
        # Generate response
        response = await ai_suite.generate_response(
            messages=messages,
            model=chat_request.model,
            temperature=chat_request.temperature
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

@router.post("/chat/server", dependencies=[Depends(verify_server_token)])
async def chat_completion_server(
    request: Request,
    chat_request: ChatRequest
):
    """
    Generate a chat completion response using the configured AI model.
    
    Args:
        request: FastAPI Request object for accessing user information
        chat_request: ChatRequest containing messages and model configuration
    
    Returns:
        JSON response containing the generated content and any tool interactions
    """
    try:
        ai_suite = initialize_ai_suite()
        
        # Convert Pydantic messages to dict format
        messages = [msg.model_dump(exclude_none=True) for msg in chat_request.messages]
        
        # Generate response
        response = await ai_suite.generate_response(
            messages=messages,
            model=chat_request.model,
            temperature=chat_request.temperature
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
