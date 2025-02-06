import logging
import json
import uuid
import socketio
from typing import Coroutine, Dict, Optional, Union
from abc import ABC, abstractmethod
from datetime import datetime
from webserver.config import settings
from webserver.ai.aw_aisuite import AiSuiteAsstTextMessage, AiSuiteAsstFunctionCall, AiSuiteAsstFunctionResult, AiSuiteAssistant
from webserver.db.chatdb.db import mongodb_client
from webserver.sbsocketio.connection_manager import ConnectionManager
from webserver.db.chatdb.models import DBMessageText, DBMessageFunctionCall, DBMessageFunctionResult
from webserver.sbsocketio.assistant_room import AssistantRoom
logger = logging.getLogger(__name__)

class AiSuiteRoom(AssistantRoom):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def initializeAiSuiteAssistant(self):
        """Initialize AISuite with configuration and tools."""
        try:
            config = {}
            
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
            
            ai_suite.set_tool_function_map(self.tool_map)
            ai_suite.set_tool_chain_config(allow_chaining=True, max_turns=8)

            self.api = ai_suite
              
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}", exc_info=True)
            raise e

    async def send_message_to_ai(self, message: dict, sid: str, userid: str, model_id: str) -> None:
        pass