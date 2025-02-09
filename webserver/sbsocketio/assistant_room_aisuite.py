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

    async def initialize(self):
        logger.info('[AiSuiteRoom] Initializing....')
        await self.initializeAiSuiteAssistant()
        logger.info('[AiSuiteRoom] Initialized')
        return True

    async def initializeAiSuiteAssistant(self):
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

            ai_suite.add_event_callback('tool_call', self._handle_function_call)
            ai_suite.add_event_callback('tool_result', self._handle_function_result)
            ai_suite.add_event_callback('final_response', self._handle_aisuite_response)
            ai_suite.add_event_callback('error', self._handle_aisuite_error)

            self.api = ai_suite
              
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}", exc_info=True)
            raise e

    async def handle_send_message(self, message: dict, sid: str, model_id: str) -> None:
        """Handle sending a message."""
        logger.info(f"[SEND MESSAGE] Handling send message in room {self.room_id}")
        if not self.chat_id:
            logger.error(f"No chat_id found for room {self.room_id}")
            return

        # Get user data from connection manager if needed
        logger.info(f"[SEND MESSAGE] Getting user data for socket {sid}")
        userid = self.connection_manager.get_user_id(sid)
        if not userid:
            logger.error(f"No user data found for user {userid}")
            return
        
        self.save_message()
        
        # TODO: format user_message into SBAWUserMessage
        # Broadcast the message to all users in the room
        logger.info(f"[SEND MESSAGE] Broadcasting message to all users in the room {self.room_id}")
        await self.broadcast(f"receive_message {self.room_id}", sid, user_message)

        
        self.send_message_to_ai(message, sid, userid, model_id)

        pass

    async def send_message_to_ai(self, message: dict, sid: str, userid: str, model_id: str) -> None:
        """Send a message to the AISuite API."""
        model_id = model_id.replace("aisuite.", "", 1)
        full_response = await self.api.generate_response([message], model_id) # Will use event callbacks for streaming responses
        pass

    async def _handle_function_call(self, function_call: AiSuiteAsstFunctionCall) -> None:
        pass

    async def _handle_function_result(self, function_result: AiSuiteAsstFunctionResult) -> None:
        pass

    async def _handle_aisuite_response(self, response: AiSuiteAsstTextMessage) -> None:
        pass

    async def _handle_aisuite_error(self, error: dict) -> None:
        pass

# TODO: _execute_tool should return the class for the result
# TODO: model_api_source -> ai_model ID/name handling