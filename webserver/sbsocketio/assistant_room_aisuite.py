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
from webserver.sbsocketio.models.models_assistant_chat import SBAWUserTextMessage, SBAWAssistantTextMessage, SBAWFunctionCall, SBAWFunctionResult
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
        
        logger.info(f"[SEND MESSAGE] Data: {message}")
        """
        {
            'type': 'sbaw.incoming.text_message.user', 
            'data': 
            {
            'item': 
                {
                'id': '1739122253019', 
                'type': 'message',
                'role': 'user', 
                'model_id': 'aisuite.openai:gpt-4o',
                'modality': 'text', 
                'content': 'asd\n'
                }
                'id': '1739122253019'
             }
        """

        message_item = message["data"]["item"]

        # Notify sender that message was received
        client_message_id = message_item.get("id")
        logger.info(f"[SEND MESSAGE] Emitting message_sent event for client message id {client_message_id}")
        await self.sio.emit(f'message_sent {client_message_id}', 
                {'success': True}, 
                room=sid, 
                namespace=self.namespace
            )

        message_id = str(uuid.uuid4())
        created_timestamp = datetime.now()
        
        # Store message in DB
        db_message = DBMessageText(
            message_id=message_id,
            chat_id=self.chat_id,
            model_id=model_id,
            model_api_source="aisuite",
            content=message_item["content"],
            role="user",
            type="message",
            modality=message_item["modality"],
            created_timestamp=created_timestamp
        )
        self.save_message(db_message.model_dump())


        # Broadcast message to all users in the room
        user_message = SBAWUserTextMessage(
            id=message_id,
            content=message_item["content"],
            model_id=model_id,
            role="user",
            type="message",
            modality="text",
            created_timestamp=created_timestamp.isoformat()
        )
        logger.info(f"[SEND MESSAGE] Broadcasting message to all users in the room {self.room_id}")
        await self.broadcast(f"receive_message {self.room_id}", sid, user_message.model_dump())

        # Send message to AI model
        message_aisuite = { "role": "user", "content": message_item['content'] }
        self.send_message_to_ai(message_aisuite, sid, userid, model_id)

    async def send_message_to_ai(self, message: dict, sid: str, userid: str, model_id: str) -> None:
        """Send a message to the AISuite API."""
        model_id = model_id.replace("aisuite.", "", 1)
        full_response = await self.api.generate_response([message], model_id) # Will use event callbacks for streaming responses

    async def _handle_function_call(self, function_call: AiSuiteAsstFunctionCall) -> None:
        # SBAWFunctionCall
        # DBMessageFunctionCall
        pass

    async def _handle_function_result(self, function_result: AiSuiteAsstFunctionResult) -> None:
        # SBAWFunctionResult
        # DBMessageFunctionResult
        pass

    async def _handle_aisuite_response(self, response: AiSuiteAsstTextMessage) -> None:
        # SBAWAssistantTextMessage, 
        # DBMessageAssistantText, 
        pass

    async def _handle_aisuite_error(self, error: dict) -> None:
        pass

# TODO: _execute_tool should return the class for the result
# TODO: model_api_source -> ai_model ID/name handling