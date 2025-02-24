import logging
import json
import uuid
from typing import Optional
from datetime import datetime
from webserver.config import settings
from webserver.sbsocketio.assistant_room import AssistantRoom
from webserver.db.chatdb.db import mongodb_client
from webserver.db.chatdb.models import DBMessageText, DBMessageFunctionCall, DBMessageFunctionResult
from assistant.assistant_realtime_openai import OpenAIRealTimeAPI
logger = logging.getLogger(__name__)

class OpenAiRealTimeRoom(AssistantRoom):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.model_id == "gpt-4o-realtime-preview-2024-12-17":
            self.api = OpenAIRealTimeAPI(settings.OPENAI_API_KEY, settings.OPENAI_REALTIME_ENDPOINT_URL)
        else:
            raise ValueError(f"Unsupported model: {self.model_id}")
        
        self.api.set_auto_execute_functions(self.auto_execute_functions)
        self.api.set_tool_call_callback(self._handle_function_result)

        self.api_connection_attempts = 0
        self.MAX_CONNECTION_ATTEMPTS = 5

    async def initialize_openai_socket(self):
        await self.api.connect()

        # Format tools for session update
        tools = []
        for name, meta in self.tool_map.items():
            logger.info(f"Tool name: {name}, meta: {meta}")
            tool = {
                "type": "function",
                "name": name,
                "description": meta["description"],
                "parameters": meta["parameters"],
            }
            tools.append(tool)

        # Set up the initial session with tools enabled
        await self.api.send_event(
            "session.update",
            {
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": "You are a helpful assistant. Please answer clearly and concisely.",
                    "temperature": 0.8,
                    "tools": tools,
                    "turn_detection": None,
                    "input_audio_transcription": {"model": "whisper-1"},
                }
            },
        )

    async def initialize_chat(self):
        if not self.chat_id:
            return

        # Load last 10 messages into conversation context
        messages_collection = mongodb_client.db["messages"]
        messages = await messages_collection.find(
            {"chat_id": self.chat_id}
        ).sort("created_timestamp", -1).limit(10).to_list(10)
        
        if self.model_id == "gpt-4o-realtime-preview-2024-12-17":
            # Add messages to conversation context in chronological order
            messages.reverse()
            for msg in messages:
                if msg.get("type") == "message":
                    await self.api.send_event(
                        "conversation.item.create",
                        {
                            "item": {
                                "id": msg.get("message_id")[:30],
                                "type": "message",
                                "role": msg.get("role"),
                                "content": [{
                                    "type": "input_text" if msg.get("role") == "user" else "text",
                                    "text": msg.get("content")
                                }],
                            }
                        }
                    )
                elif msg.get("type") == "function_call":
                    await self.api.send_event(
                        "conversation.item.create",
                        {
                            "item": {
                                "id": msg.get("message_id")[:30],
                                    "call_id": msg.get("call_id"),
                                    "type": "function_call",
                                    "name": msg.get("name"),
                                    "arguments": msg.get("arguments")
                                }
                            }
                        )
        else:
            raise ValueError(f"Unsupported model: {self.model_id}")

    async def initialize(self):
        """Initialize the OpenAI API connection and set up event handlers"""
        try:
            # Register generic callback for all events
            self.api.register_event_callback("error", self._handle_openai_error)
            self.api.register_event_callback("response.done", self._handle_openai_response_done)
            self.api.register_event_callback("response.audio.delta", self._handle_openai_rt_generic)
            self.api.register_event_callback("response.audio_transcript.delta", self._handle_openai_rt_generic)
            self.api.register_event_callback("response.text.delta", self._handle_openai_rt_generic)
            self.api.register_event_callback("response.audio_transcript.done", self._handle_openai_rt_generic)
            self.api.register_event_callback("conversation.item.input_audio_transcription.completed", self._handle_openai_rt_generic)

            # Register tool functions with API
            self.api.set_tool_function_map(self.tool_map)

            # Connect to OpenAI
            await self.initialize_openai_socket()

            # Initialize chat
            await self.initialize_chat()
            
            logger.info(f"Room {self.room_id} initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing room {self.room_id}: {e}", exc_info=True)
            return False
        
    async def _handle_function_result(self, tool_call: dict, result: dict) -> None:
        """Handle tool call callback"""
        logger.info(f"[TOOL CALL] Received tool call callback in room {self.room_id}: {tool_call.get('call_id')} {result}")
        messageid = str(uuid.uuid4())
        function_call = tool_call.get('function')
        timestamp = tool_call.get('timestamp')
        
        db_message = DBMessageFunctionResult(
            message_id=messageid,
            chat_id=self.chat_id,
            model_id=self.model_id,
            model_api_source="openai_realtime",
            created_timestamp=timestamp,
            role="system",
            type="function_result",
            name=function_call.get('name'),
            arguments=json.dumps(function_call.get('arguments')),
            call_id=tool_call.get('call_id'),
            result=result
        )
        
        save_message_result = await self.save_message(db_message.model_dump())
        logger.info(f"[FUNCTION RESULT] Saving function result for message_id {messageid}")

        function_result_message = {
            "type": "response.sb.function_result.done",
            "response": {
                "message_id": messageid,
                "chat_id": self.chat_id,
                "created_timestamp": timestamp,
                "role": "system",
                "type": "function_result",
                "name": function_call.get('name'),
                "arguments": function_call.get('arguments'),
                "call_id": tool_call.get('call_id'),
                "result": result,
            }
        }

        await self.broadcast(f"receive_message {self.room_id}", None, function_result_message)
        return
        
    async def _handle_openai_response_done(self, event: dict) -> None:
        """Handle all messages from OpenAI and broadcast to room."""
        logger.info(f"[OPENAI EVENT] Received OpenAI event in room {self.room_id}: {event}")
        try:
            event_type = event.get("type")

            logger.debug(f"Received OpenAI event in room {self.room_id}: {event_type}")

            if event_type == "response.done":
                response = event.get('response')
                if not response:
                    logger.error(f"No response found in event {event}")
                    return
                output = response.get('output')
                if not output:
                    logger.error(f"No output found in response {response}")
                    return
                output_item = None
                if len(output) > 1:
                    logger.warning(f"[OPENAI EVENT] [RESPONSE.DONE] Multiple outputs found in response {response}")
                    output_item = output[0]
                elif len(output) == 1:
                    output_item = output[0]
                else:
                    logger.error(f"[OPENAI EVENT] [RESPONSE.DONE] No output found in response {response}")
                    return
                if output_item.get('type') == "message":
                    output_item_content_list = output_item.get('content')
                    if not output_item_content_list:
                        logger.error(f"[OPENAI EVENT] [RESPONSE.DONE] No content found in response message {output_item}")
                        return
                    if len(output_item_content_list) > 1:
                        logger.warning(f"[OPENAI EVENT] [RESPONSE.DONE] Multiple content found in response content {output_item_content_list}")
                    content_item = output_item_content_list[0]
                    content_item_type = content_item.get('type')
                    content_item_text = None
                    if content_item_type == "text":
                        content_item_text = content_item.get('text')
                    elif content_item_type == "audio":
                        content_item_text = content_item.get('transcript')
                    else:
                        logger.warning(f"[OPENAI EVENT] [RESPONSE.DONE] Invalid response message type {content_item_type}")
                        return

                    messageid = str(uuid.uuid4())
                    created_timestamp = datetime.now()
                    role = output_item.get('role')
                    model_id = self.model_id
                    usage = event.get('usage')
                    db_message = DBMessageText(
                        message_id=messageid,
                        chat_id=self.chat_id,
                        model_id=model_id,
                        model_api_source="openai_realtime",
                        created_timestamp=created_timestamp,
                        role=role,
                        content=content_item_text,

                        modality=content_item_type,
                        type="message",
                        usage=usage,
                    )
                    save_message_result = await self.save_message(db_message.model_dump())
                if output_item.get('type') == "function_call":
                    messageid = str(uuid.uuid4())


                    created_timestamp = datetime.now()
                    role = "system"
                    model_id = self.model_id
                    usage = response.get('usage')
                    db_message = DBMessageFunctionCall(
                        message_id=messageid,
                        chat_id=self.chat_id,
                        model_id=model_id,
                        model_api_source="openai_realtime",
                        created_timestamp=created_timestamp,
                        role=role,

                        type="function_call",
                        usage=usage,
                        name=output_item.get('name'),
                        arguments=output_item.get('arguments'),
                        call_id=output_item.get('call_id'),
                    )
                    save_message_result = await self.save_message(db_message.model_dump())
                # Broadcast the message to all users in the room
                logger.info(f"[OPENAI EVENT] [RESPONSE.DONE] Broadcasting message to all users in the room {self.room_id}")
                await self.broadcast(f"receive_message {self.room_id}", None, event)

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing OpenAI event in room {self.room_id}: {e}")
        except Exception as e:
            logger.error(
                f"Error handling OpenAI event in room {self.room_id}: {e}",
                exc_info=True,
            )

    async def _handle_openai_rt_generic(self, event: dict) -> None:
        """Handle generic OpenAI events"""
        if (event.get("type") != "response.audio.delta"):
            logger.info(f"[OPENAI EVENT] [GENERIC] Received OpenAI event in room {self.room_id}: {event}")
        await self.broadcast(f"receive_message {self.room_id}", None, event)

    async def _handle_openai_error(
        self, error: str, event: Optional[dict] = None
    ) -> None:
        """Handle errors from OpenAI."""
        logger.error(f"OpenAI error in room {self.room_id}: {error}")
        if isinstance(error, dict) and error.get('error', {}).get('code') == 'session_expired':
            logger.info(f"Session expired for room {self.room_id}, cleaning up")
            await self.broadcast(f"error {self.room_id}", None, {"error": "OpenAI Realtime session has expired"})
            await self.cleanup()

    async def _handle_send_message(self, message: dict, sid: str, model_id: str) -> None:
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
        
        if message.get("type") == "conversation.item.create":
            # Format user message for broadcasting to other users
            user_message = {
                "room_id": self.room_id,
                "message": message,
                'type': 'user.message',
            }
        
            # Broadcast the message to all users in the room
            logger.info(f"[SEND MESSAGE] Broadcasting message to all users in the room {self.room_id}")
            await self.broadcast(f"receive_message {self.room_id}", sid, user_message)

        # Send message sent event to client
        client_message_id = message.get("id")
        logger.info(f"[SEND MESSAGE] Emitting message_sent event for client message id {client_message_id}")
        await self.sio.emit(f'message_sent {client_message_id}', 
                {'success': True}, 
                room=sid, 
                namespace=self.namespace
            )

        # Send the message to the AI
        await self.send_message_to_ai(message, sid, userid,model_id)

    async def send_message_to_ai(self, message: dict, sid: str, userid: str, model_id: str) -> None:
        """Send a message to the OpenAI API."""
        try:       
            if not self.api.is_connected():
                if self.api_connection_attempts > self.MAX_CONNECTION_ATTEMPTS:
                    logger.error("[SEND MESSAGE] [OPENAI WEBSOCKET] Max connection attempts reached")
                    return

                logger.warning(f"[SEND MESSAGE] [OPENAI WEBSOCKET] OpenAI API is not connected, attempting to reconnect #{self.api_connection_attempts} {self.room_id}")
                await self.initialize_openai_socket()

            # If not a user conversation message, just send it to the API
            if message.get("type") != "conversation.item.create":
                logger.info(f"[SEND MESSAGE] Not a conversation.item.create")
                await self.api.send_event(
                    event_type=message["type"], data=message.get("data", {})
                )
                return

            logger.info(f"[SEND MESSAGE] ", message)

            # Extract auto_execute setting from message if present
            auto_execute = message.get("auto_execute_functions", False)
            self.api.set_auto_execute_functions(auto_execute)

            raw_chat_message = message["data"]["item"]
            chat_message_content = raw_chat_message["content"][0]["text"]

            role = "user"
            messageid = str(uuid.uuid4())
            created_timestamp = datetime.now()
            modality = "text"

            db_message = DBMessageText(
                message_id=messageid,
                chat_id=self.chat_id,
                user_id=userid,
                model_id=model_id,
                model_api_source="openai_realtime",
                created_timestamp=created_timestamp,
                role=role,
                content=chat_message_content,
                modality=modality,
                type="message"
            )
            save_message_result = await self.save_message(db_message.model_dump())

            # Send the actual message
            logger.info(f"[SEND MESSAGE] Sending message to AI: {message}")
            await self.api.send_event(
                event_type=message["type"], data=message.get("data", {})
            )

            
        except Exception as e:
            logger.error(
                f"Error sending message in room {self.room_id}: {e}", exc_info=True
            )
            raise e

    async def cleanup(self):
        """Cleanup room resources"""
        try:
            await self.api.disconnect()
            logger.info(f"Room {self.room_id} cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up room {self.room_id}: {e}")