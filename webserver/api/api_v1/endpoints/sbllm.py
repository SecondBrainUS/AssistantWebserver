import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from assistant.sb_llm import SBLLM
from assistant.sb_llm_assistant import SbLlmAssistant
from assistant.assistant_functions import AssistantFunctions
from webserver.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

def initialize_assistant(provider: str, model: str) -> SbLlmAssistant:
    """Initialize SBLLM client and assistant with registered tools."""
    try:
        # Initialize LLM client
        llm_config = {
            "api_key": settings.OPENAI_API_KEY,
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY
        }
        sb_llm = SBLLM(provider=provider, **llm_config)
        
        # Create assistant with default configuration
        assistant = SbLlmAssistant(
            llm=sb_llm,
            model=model,
            system_prompt=settings.ASSISTANT_SYSTEM_PROMPT,
            auto_execute_functions=True
        )
        
        # Initialize and register assistant functions
        assistant_functions = AssistantFunctions(
            openai_api_key=settings.OPENAI_API_KEY,
            notion_api_key=settings.NOTION_API_KEY,
            gcal_credentials_path=settings.GCAL_CREDENTIALS_PATH
        )
        
        for name, tool in assistant_functions.get_tool_function_map().items():
            assistant.register_tool(
                name=name,
                function=tool["function"],
                description=tool["description"],
                parameters=tool["parameters"]
            )
            
        return assistant
        
    except Exception as e:
        logger.error(f"Initialization error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Assistant initialization failed")

@router.post("/")
async def process_message(
    provider: str = "openai",
    model: str = "gpt-4-turbo",
    messages: List[Dict[str, Any]] = [{"role": "user", "content": "Say this is a test"}]
):
    try:
        # Initialize assistant with tools
        assistant = initialize_assistant(provider, model)
        
        # Process message chain
        response = await assistant.process_message(messages[-1]["content"])
        
        return {
            "content": response.content,
            "tool_calls": response.tool_calls,
            "token_usage": response.token_usage
        }
        
    except Exception as e:
        logger.error(f"Processing error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
