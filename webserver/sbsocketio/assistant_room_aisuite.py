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
from webserver.db.chatdb.models import DBMessageText, DBMessageFunctionCall, DBMessageFunctionResult, DBMessageAssistantText
from webserver.sbsocketio.models.models_assistant_chat import SBAWUserTextMessage, SBAWAssistantTextMessage, SBAWFunctionCall, SBAWFunctionResult
from webserver.sbsocketio.assistant_room import AssistantRoom
from prometheus_client import Counter

# Prometheus metrics
AISUITE_FUNCTION_CALLS = Counter('aisuite_function_calls_total', 'Total function calls by name', ['function_name'])
AISUITE_FUNCTION_RESULTS = Counter('aisuite_function_results_total', 'Total function results by name', ['function_name'])
AISUITE_USER_MESSAGES = Counter('aisuite_user_messages_total', 'Total user messages received')
AISUITE_AI_RESPONSES = Counter('aisuite_ai_responses_total', 'Total AI responses generated')
AISUITE_AI_ERRORS = Counter('aisuite_ai_errors_total', 'Total AI errors encountered')

logger = logging.getLogger(__name__)

class AiSuiteRoom(AssistantRoom):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def initialize(self):
        logger.info('[AiSuiteRoom] Initializing....')
        await self.initializeAiSuiteAssistant()
        # Load conversation history after initializing the assistant
        await self.initialize_chat()
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

            if settings.XAI_API_KEY:
                config["xai"] = {"api_key": settings.XAI_API_KEY}
                
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                config["aws"] = {
                    "access_key_id": settings.AWS_ACCESS_KEY_ID,
                    "secret_access_key": settings.AWS_SECRET_ACCESS_KEY
                }
        
            if settings.GROQ_API_KEY:
                config["groq"] = {"api_key": settings.GROQ_API_KEY}
            
            ai_suite = AiSuiteAssistant(config=config)
            
            # Add tool usage guide to system prompt if it exists
            if self.tool_usage_guide:
                self.set_system_prompt(self.tool_usage_guide)
            
            ai_suite.set_tool_function_map(self.tool_map)
            ai_suite.set_tool_chain_config(allow_chaining=True, max_turns=30)

            ai_suite.add_event_callback('tool_call', self._handle_function_call)
            ai_suite.add_event_callback('tool_result', self._handle_function_result)
            ai_suite.add_event_callback('final_response', self._handle_aisuite_response)
            ai_suite.add_event_callback('error', self._handle_aisuite_error)

            self.api = ai_suite

            self.conversation_history = []
              
        except Exception as e:
            logger.error(f"Initialization error: {str(e)}", exc_info=True)
            raise e

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt and add it to conversation history."""
        if hasattr(self, 'api'):
            self.api.set_system_prompt(prompt)
        
        # Initialize conversation_history if it doesn't exist
        if not hasattr(self, 'conversation_history'):
            self.conversation_history = []
            
        # Remove any existing system messages
        self.conversation_history = [msg for msg in self.conversation_history if msg.get('role') != 'system']
        
        # Add the new system prompt as the first message
        self.conversation_history.insert(0, {
            "role": "system",
            "content": prompt
        })

    async def initialize_chat(self):
        """Load conversation history from MongoDB."""
        if not self.chat_id:
            return

        # Load last 10 messages into conversation context
        messages_collection = mongodb_client.db["messages"]
        messages = await messages_collection.find(
            {"chat_id": self.chat_id}
        ).sort("created_timestamp", -1).limit(10).to_list(10)
        
        # Convert messages to format expected by AISuite
        self.conversation_history = []
        for msg in reversed(messages):  # Reverse to get chronological order
            if msg.get("type") == "message":
                self.conversation_history.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })

    async def _handle_send_message(self, message: dict, sid: str, model_id: str) -> None:
        """Handle sending a message."""
        super()._handle_send_message(message, sid, model_id)

        AISUITE_USER_MESSAGES.inc()
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

        message_item = message["data"]["item"]

        # Notify sender that message was received
        client_message_id = message.get("id")
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
        await self.save_message(db_message.model_dump())

        # Broadcast message to all users in the room
        user_text_message = SBAWUserTextMessage(
            id=message_id,
            content=message_item["content"],
            model_id=model_id,
            role="user",
            type="message",
            modality="text",
            created_timestamp=created_timestamp.isoformat()
        )

        message_event = {
            "type": "sbaw.text_message.user",
            "data": user_text_message.model_dump()
        }

        logger.info(f"[SEND MESSAGE] Broadcasting message to all users in the room {self.room_id}")
        await self.broadcast(f"receive_message {self.room_id}", sid, message_event)

        # Send message to AI model
        message_aisuite = { "role": "user", "content": message_item['content'] }
        try:
            await self.send_message_to_ai(message_aisuite, sid, userid, model_id)
        except Exception as e:
            logger.error(f"[SEND MESSAGE] Error sending message to AI: {e}")
            await self.sio.emit(f'message_error {client_message_id}', 
                {'error': str(e)}, 
                room=sid, 
                namespace=self.namespace)
            await self.sio.emit(f'message_error', 
                {'error': str(e), 'message_id': message_id, 'client_message_id': client_message_id}, 
                room=self.room_id,
                namespace=self.namespace)

    async def send_message_to_ai(self, message: dict, sid: str, userid: str, model_id: str) -> None:
        """Send a message to the AISuite API."""
        model_id = model_id.replace("aisuite.", "", 1)
        
        self.conversation_history.append(message)
        
        # Uses event callbacks for streaming the responses
        full_response = await self.api.generate_response(self.conversation_history, model_id)

    async def _handle_function_call(self, function_call: AiSuiteAsstFunctionCall) -> None:
        logger.info(f"[HANDLE AISUITE FUNCTION CALL] {function_call}")
        await super()._handle_function_call(function_call.name)
        AISUITE_FUNCTION_CALLS.labels(function_name=function_call.name).inc()

        message_id = str(uuid.uuid4())
        created_timestamp = datetime.now()

        # Add function call to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": function_call.call_id,
                "type": "function",
                "function": {
                    "name": function_call.name,
                    "arguments": json.dumps(function_call.arguments)
                }
            }]
        })

        # Store message in DB
        db_message = DBMessageFunctionCall(
            message_id=message_id,
            chat_id=self.chat_id,
            model_id=function_call.model_id,
            model_api_source="aisuite",
            usage=function_call.token_usage,
            name=function_call.name,
            arguments=json.dumps(function_call.arguments),
            call_id=function_call.call_id,
            role="assistant",
            type="function_call",
            created_timestamp=created_timestamp
        )
        await self.save_message(db_message.model_dump())

        # Broadcast message to all users in the room
        assistant_message = SBAWFunctionCall(
            id=message_id,
            call_id=function_call.call_id,
            name=function_call.name,
            arguments=function_call.arguments,
            created_timestamp=created_timestamp.isoformat()
        )

        message_event = {
            "type": "sbaw.function_call",
            "data": assistant_message.model_dump()
        }
        logger.info(f"[HANDLE FUNCTION CALL] Broadcasting message to all users in the room {self.room_id}")
        await self.broadcast(f"receive_message {self.room_id}", None, message_event)

    async def _handle_function_result(self, function_result: AiSuiteAsstFunctionResult) -> None:
        logger.info(f"[HANDLE FUNCTION RESULT] {function_result}")
        await super()._handle_function_result(function_result.name)
        AISUITE_FUNCTION_RESULTS.labels(function_name=function_result.name).inc()

        message_id = str(uuid.uuid4())
        created_timestamp = datetime.now()

        # Add function result to conversation history
        self.conversation_history.append({
            "role": "tool",
            "tool_call_id": function_result.call_id,
            "name": function_result.name,
            "content": json.dumps({
                "result": function_result.result,
                "arguments": function_result.arguments
            })
        })

        # Store message in DB
        db_message = DBMessageFunctionResult(
            message_id=message_id,
            chat_id=self.chat_id,
            model_id=function_result.model_id,
            model_api_source="aisuite",
            call_id=function_result.call_id,
            name=function_result.name,
            arguments=json.dumps(function_result.arguments),
            result=function_result.result,
            role="assistant",
            type="function_result",
            created_timestamp=created_timestamp
        )
        await self.save_message(db_message.model_dump())

        # Broadcast message to all users in the room
        assistant_message = SBAWFunctionResult(
            id=message_id,
            call_id=function_result.call_id,
            name=function_result.name,
            result=function_result.result,
            created_timestamp=created_timestamp.isoformat()
        )

        message_event = {
            "type": "sbaw.function_result",
            "data": assistant_message.model_dump()
        }
        logger.info(f"[HANDLE FUNCTION RESULT] Broadcasting message to all users in the room {self.room_id}")
        await self.broadcast(f"receive_message {self.room_id}", None, message_event)

    async def _handle_aisuite_response(self, response: AiSuiteAsstTextMessage) -> None:
        logger.info(f"[HANDLE AISUITE RESPONSE] {response}")
        await super()._handle_response()
        AISUITE_AI_RESPONSES.inc()

        message_id = str(uuid.uuid4())
        created_timestamp = datetime.now()

        # Add assistant response to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content
        })

        # Store message in DB
        db_message = DBMessageAssistantText(
            message_id=message_id,
            chat_id=self.chat_id,
            model_id=response.model_id,
            model_api_source="aisuite",
            content=response.content,
            role="assistant",
            type="message",
            modality="text",
            usage=response.token_usage,
            created_timestamp=created_timestamp
        )
        await self.save_message(db_message.model_dump())

        # Broadcast message to all users in the room
        assistant_message = SBAWAssistantTextMessage(
            id=message_id,
            content=response.content,
            model_id=response.model_id,
            token_usage=response.token_usage,
            stop_reason=response.stop_reason,
            created_timestamp=created_timestamp.isoformat()
        )

        message_event = {
            "type": "sbaw.text_message.assistant",
            "data": assistant_message.model_dump()
        }
        logger.info(f"[HANDLE AISUITE RESPONSE] Broadcasting message to all users in the room {self.room_id}")
        await self.broadcast(f"receive_message {self.room_id}", None, message_event)

    async def _handle_aisuite_error(self, error: dict) -> None:
        """Handle errors from the AISuite API."""
        logger.error(f"[HANDLE AISUITE ERROR] Error from AISuite: {error}")
        await super()._handle_error(str(error.get("message", "Unknown error")))
        AISUITE_AI_ERRORS.inc()
        
        message_id = str(uuid.uuid4())
        created_timestamp = datetime.now()
        
        error_message = {
            "type": "sbaw.error",
            "data": {
                "id": message_id,
                "error": str(error.get("message", "Unknown error occurred")),
                "created_timestamp": created_timestamp.isoformat()
            }
        }
        
        # Broadcast error to all users in the room
        await self.broadcast(f"receive_message {self.room_id}", None, error_message)
        
        # Also emit a specific error event
        await self.sio.emit(
            "error",
            {"error": str(error.get("message", "Unknown error occurred"))},
            room=self.room_id,
            namespace=self.namespace
        )

    async def _handle_room_event(self, event: dict, sid: str) -> None:
        logger.info(f"[AISUITE ROOM] [HANDLE ROOM EVENT] {event}")

        event_type = event.get("type")
        if not event_type:
            logger.warning(f"[AISUITE ROOM] [HANDLE ROOM EVENT] No event type found in event: {event}")
            return

        if event_type == "sbaw.assistant.stop_processing":
            self.stop_processing()

        if event_type == "sbaw.assistant.update_session":
            self.update_session()

        client_event_id = event.get("id")
        logger.info(f"[AISUITE ROOM] [HANDLE ROOM EVENT] Emitting event_received event for client event id {client_event_id}")
        await self.sio.emit(f'event_received {client_event_id}', 
                {'success': True}, 
                room=sid, 
                namespace=self.namespace
            )
        
    # TODO: next
    def update_session(self):
        #self.conversation_history_length = 
        #ai_suite.set_tool_chain_config(allow_chaining=True, max_turns=30)
        pass

    def stop_processing(self):
        """Request to stop the current processing"""
        self.api.stop_processing()

# TODO: _execute_tool should return the class for the result
# TODO: model_api_source -> ai_model ID/name handling