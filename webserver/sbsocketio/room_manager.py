import logging
import asyncio
import json
import uuid
from typing import Dict, Optional
from datetime import datetime
from assistant_realtime_openai import OpenAIRealTimeAPI
from assistant_functions import AssistantFunctions
import socketio
from webserver.config import settings
from webserver.db.chatdb.db import mongodb_client
from webserver.sbsocketio.connection_manager import ConnectionManager
from bson import Binary
from uuid import UUID
from webserver.db.chatdb.uuid_utils import uuid_to_binary, ensure_uuid
logger = logging.getLogger(__name__)

async def save_message(message: dict):
    """Save a message to the database"""
    message_id = message["message_id"]
    try:
        # Use our utility function that handles the conversion properly
        message["message_id"] = uuid_to_binary(message_id)
        if "chat_id" in message:
            message["chat_id"] = uuid_to_binary(message["chat_id"])
        if "user_id" in message:
            message["user_id"] = ensure_uuid(message["user_id"])
            
        messages_collection = mongodb_client.db["messages"]
        await messages_collection.insert_one(message)
        logger.info(f"Message saved for message_id {message_id}")
        return {"success": True, "message_id": message_id}
    except Exception as e:
        logger.error(
            f"Error saving message for message_id {message_id}: {e}", exc_info=True
        )
        return {"error": str(e)}


async def save_chat(chat: dict):
    """Save a chat to the database"""
    chat_id = chat["chat_id"]
    try:
        # Use our utility function that handles the conversion properly
        chat["chat_id"] = uuid_to_binary(chat_id)
        if "user_id" in chat:
            chat["user_id"] = ensure_uuid(chat["user_id"])
            
        chats_collection = mongodb_client.db["chats"]
        await chats_collection.insert_one(chat)
        logger.info(f"Chat saved for chat_id {chat_id}")
        return {"success": True, "chat_id": chat_id}
    except Exception as e:
        logger.error(f"Error saving chat for chat_id {chat_id}: {e}", exc_info=True)
        return {"error": str(e)}


class AssistantRoom:
    def __init__(
        self,
        room_id: str,
        namespace: str,
        model: str,
        api_key: str,
        endpoint_url: str,
        connection_manager: ConnectionManager,
        auto_execute_functions: bool = False,
        sio: socketio.AsyncServer = None,
        chat_id: Optional[str] = None,
    ):
        """ """
        self.room_id = room_id
        self.model = model

        # Create model instance
        if model == "OpenAI GPT-4o Realtime Preview 2024-12-17":
            self.api = OpenAIRealTimeAPI(api_key, endpoint_url)
        else:
            raise ValueError(f"Unsupported model: {model}")
        self.api.set_auto_execute_functions(auto_execute_functions)
        self.api.set_tool_call_callback(self._handle_function_result)
        
        self.connected_users: set[str] = set()
        self.message_count = 0
        self.connection_manager = connection_manager
        
        if chat_id:
            self.chat_id = chat_id

        self._aiapi_connection_attempt = 0
        self.MAX_CONNECTION_ATTEMPTS = 5

        # Initialize AssistantFunctions
        self.assistant_functions = AssistantFunctions(
            openai_api_key=settings.OPENAI_API_KEY,
            notion_api_key=settings.NOTION_API_KEY,
            notion_running_list_database_id=settings.NOTION_RUNNING_LIST_DATABASE_ID,
            notion_notes_page_id=settings.NOTION_NOTES_PAGE_ID,
            gcal_credentials_path=settings.GCAL_CREDENTIALS_PATH,
            gcal_token_path=settings.GCAL_TOKEN_PATH,
            gcal_auth_method="service_account",
            sensor_values_host=settings.SENSOR_VALUES_HOST_CRITTENDEN,
            sensor_values_metrics=settings.SENSOR_VALUES_METRICS,
            sensor_values_group_id=settings.SENSOR_VALUES_CRITTENDEN_GROUP_ID,
        )

        # Store message callback for broadcasting
        self._message_callback = None
        self._message_error_callback = None

        self.sio = sio  # Add Socket.IO instance

    def set_chat_id(self, chat_id: str):
        """Set the chat ID associated with this room"""
        self.chat_id = chat_id
        logger.info(f"Set chat_id {chat_id} for room {self.room_id}")

    async def initialize_openai_socket(self):
        tool_map = self.assistant_functions.get_tool_function_map()

        await self.api.connect()

        # Format tools for session update
        tools = []
        for name, meta in tool_map.items():
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
        
        if self.model == "OpenAI GPT-4o Realtime Preview 2024-12-17":
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
            raise ValueError(f"Unsupported model: {self.model}")

    async def initialize(self):
        """Initialize the OpenAI API connection and set up event handlers"""
        try:
            # Register generic callback for all events
            self.api.register_event_callback("error", self._handle_openai_error)
            self.api.register_event_callback("response.done", self._handle_openai_response_done)

            # Get tool function map
            tool_map = self.assistant_functions.get_tool_function_map()

            # Register tool functions with API
            self.api.set_tool_function_map(tool_map)

            # Connect to OpenAI
            await self.initialize_openai_socket()

            # Initialize chat
            await self.initialize_chat()
            
            logger.info(f"Room {self.room_id} initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing room {self.room_id}: {e}", exc_info=True)
            return False

    def set_message_callback(self, callback: callable) -> None:
        """Set the callback for broadcasting messages to room members."""
        self._message_callback = callback

    def set_message_error_callback(self, callback: callable) -> None:
        """Set the callback for sending error messages to the original sender."""
        self._message_error_callback = callback

    async def _handle_function_result(self, tool_call: dict, result: dict) -> None:
        """Handle tool call callback"""
        logger.info(f"[TOOL CALL] Received tool call callback in room {self.room_id}: {tool_call.get('call_id')} {result}")
        messageid = str(uuid.uuid4())
        function_call = tool_call.get('function')
        save_message_result = await save_message({ 
            "message_id": messageid,
            "chat_id": self.chat_id,
            "created_timestamp": datetime.now(),
            "role": "system",
            "type": "function_result",
            "name": function_call.get('name'),
            "arguments": function_call.get('arguments'),
            "call_id": tool_call.get('call_id'),
            "result": result,
        })

        # TODO: issue, need to send the message to the room
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
                #   type": "function_call",
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
                    model = "OpenAI GPT-4o Realtime Preview 2024-12-17"
                    usage = event.get('usage')
                    save_message_result = await save_message({ 
                        "message_id": messageid,
                        "chat_id": self.chat_id,
                        "model": model,
                        "created_timestamp": created_timestamp,
                        "role": role,
                        "content": content_item_text,
                        "modality": content_item_type,
                        "type": "message",
                        "usage": usage,
                    })
                if output_item.get('type') == "function_call":
                    messageid = str(uuid.uuid4())
                    created_timestamp = datetime.now()
                    role = "system"
                    model = "OpenAI GPT-4o Realtime Preview 2024-12-17"
                    usage = response.get('usage')
                    save_message_result = await save_message({ 
                        "message_id": messageid,
                        "chat_id": self.chat_id,
                        "model": model,
                        "created_timestamp": created_timestamp,
                        "role": role,
                        "type": "function_call",
                        "usage": usage,
                        "name": output_item.get('name'),
                        "arguments": output_item.get('arguments'),
                        "call_id": output_item.get('call_id'),
                    })
                    return

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing OpenAI event in room {self.room_id}: {e}")
        except Exception as e:
            logger.error(
                f"Error handling OpenAI event in room {self.room_id}: {e}",
                exc_info=True,
            )

    async def _handle_openai_error(
        self, error: str, event: Optional[dict] = None
    ) -> None:
        """Handle errors from OpenAI."""
        logger.error(f"OpenAI error in room {self.room_id}: {error}")
        
        # Check if error is a dict containing session expiration info
        if isinstance(error, dict) and error.get('error', {}).get('code') == 'session_expired':
            logger.info(f"Session expired for room {self.room_id}, cleaning up")
            await self.cleanup()
            # Signal room manager to remove this room
            if self._message_callback:
                await self._message_callback({
                    "event_type": "error",
                    "data": {"error": "Chat session has expired"},
                    "room_id": self.room_id
                })
            return

        # Handle other errors as before
        if self._message_callback:
            await self._message_callback({
                "event_type": "error",
                "data": {"error": error, "event": event},
                "room_id": self.room_id
            })

    async def _handle_message_error(
        self,
        error: str,
        message: Optional[dict] = None,
        sender_sid: Optional[str] = None,
    ) -> None:
        """Handle errors related to user messages."""
        logger.error(f"Message error in room {self.room_id}: {error}")
        if message:
            logger.debug(f"Error message details: {message}")

        # Send error to the original sender if callback is set and sender_sid is provided
        if self._message_error_callback and sender_sid:
            await self._message_error_callback(
                {
                    "event_type": "message_error",
                    "data": {"error": error, "message": message},
                    "room_id": self.room_id,
                    "sender_sid": sender_sid,
                }
            )

    async def send_message(self, message: dict, sid: str, model: str) -> None:
        """Send a message to the OpenAI API."""
        try:       
            if not self.api.is_connected():
                if self._aiapi_connection_attempt > self.MAX_CONNECTION_ATTEMPTS:
                    logger.error("[SEND MESSAGE] [OPENAI WEBSOCKET] Max connection attempts reached")
                    return

                logger.warning(f"[SEND MESSAGE] [OPENAI WEBSOCKET] OpenAI API is not connected, attempting to reconnect #{self._aiapi_connection_attempt} {self.room_id}")
                await self.initialize_openai_socket()

            # Get user data from connection manager if needed
            logger.info(f"[SEND MESSAGE] Getting user data for socket {sid}")
            userid = self.connection_manager.get_user_id(sid)
            if not userid:
                logger.error(f"No user data found for user {userid}")
                return

            # If not a user conversation message, just send it to the API
            if message.get("type") != "conversation.item.create":
                logger.info(f"[SEND MESSAGE] Not a conversation.item.create")
                await self.api.send_event(
                    event_type=message["type"], data=message.get("data", {})
                )
                return

            logger.info(f"[SEND MESSAGE] ", message)

            # chat_id = message.get("chat_id")
            if not self.chat_id:
                # TODO: add background task to name the chat by LLM, update the chat with the name by ID
                chat_id = str(uuid.uuid4())
                chat = {
                    "chat_id": chat_id,
                    "user_id": userid,
                    "created_timestamp": datetime.now(),
                }
                self.chat_id = chat_id
                save_chat_result = await save_chat(chat)
                if save_chat_result.get("success"):
                    logger.info(f"[SEND MESSAGE] Saved chat")
                    # Emit chat_created event with the new chat_id
                    if self._message_callback:
                        await self._message_callback({
                            "event_type": "chat_created",
                            "data": {"chat_id": chat_id},
                            "room_id": self.room_id
                        })
                else:
                    logger.error(f"[SEND MESSAGE] Error saving chat: {save_chat_result.get('error')}")
                    return

            self.message_count += 1
            # Extract auto_execute setting from message if present
            auto_execute = message.get("auto_execute_functions", False)
            self.api.set_auto_execute_functions(auto_execute)

            raw_chat_message = message["data"]["item"]

            # Verify message type and content type
            if raw_chat_message["type"] != "conversation.item.create":
                logger.error(
                    f"[SEND MESSAGE] Message is not a conversation.item.create: {raw_chat_message['type']}"
                )
                # await self._handle_message_error("Invalid message type", message=message, sender_sid=message.get("sender_sid"))
                # return
            if raw_chat_message["content"][0]["type"] != "input_text":
                logger.error(
                    f"[SEND MESSAGE] Message is not an input_text: {raw_chat_message['content'][0]['type']}"
                )
                # await self._handle_message_error("Invalid content type", message=message, sender_sid=message.get("sender_sid"))
                # return

            chat_message_content = raw_chat_message["content"][0]["text"]

            role = "user"
            messageid = str(uuid.uuid4())
            created_timestamp = datetime.now()
            modality = "text"

            save_message_result = await save_message(
                {
                    "message_id": messageid,
                    "chat_id": self.chat_id,
                    "user_id": userid,
                    "model": model,
                    "created_timestamp": created_timestamp,
                    "role": role,
                    "content": chat_message_content,
                    "modality": modality,
                    "type": "message",
                }
            )

            # Send the actual message
            logger.info(f"[SEND MESSAGE] HERE FUCKING NOTHING {message}")
            await self.api.send_event(
                event_type=message["type"], data=message.get("data", {})
            )
            
        except Exception as e:
            logger.error(
                f"Error sending message in room {self.room_id}: {e}", exc_info=True
            )
            raise

    def add_user(self, sid: str):
        """Add a user to the room"""
        self.connected_users.add(sid)
        logger.info(f"User {sid} added to room {self.room_id}")

    def remove_user(self, sid: str):
        """Remove a user from the room"""
        self.connected_users.discard(sid)
        logger.info(f"User {sid} removed from room {self.room_id}")

    async def cleanup(self):
        """Cleanup room resources"""
        try:
            await self.api.disconnect()
            logger.info(f"Room {self.room_id} cleaned up successfully")
        except Exception as e:
            logger.error(f"Error cleaning up room {self.room_id}: {e}")

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast a message to all users in the room"""
        await self.sio.emit(
            event_type,
            data,
            room=self.room_id,
            namespace='/assistant'  # adjust namespace as needed
        )


class AssistantRoomManager:
    def __init__(self, api_key: str, endpoint_url: str, connection_manager, sio: socketio.AsyncServer):
        self.sio: socketio.AsyncServer = sio
        self.rooms: Dict[str, AssistantRoom] = {}
        self.chatid_roomid_map: Dict[str, str] = {}
        self.api_key = api_key
        self.endpoint_url = endpoint_url
        self.connection_manager = connection_manager

    async def create_room(self, room_id: str, namespace: str, model: str, chat_id: str) -> bool:
        """Create a new room with OpenAI API instance"""
        if room_id in self.rooms:
            logger.warning(f"Room {room_id} already exists")
            return False

        room = AssistantRoom(
            room_id, 
            namespace,
            model,
            self.api_key, 
            self.endpoint_url, 
            self.connection_manager,
            sio=self.sio,
            chat_id=chat_id
        )
        success = await room.initialize()

        if success:
            self.rooms[room_id] = room
            self.chatid_roomid_map[chat_id] = room_id
            logger.info(f"Room {room_id} for chat {chat_id} created successfully")
            return True
        else:
            logger.error(f"Failed to create room {room_id}")
            return False

    def get_room(self, room_id: str) -> Optional[AssistantRoom]:
        """Get a room by ID"""
        return self.rooms.get(room_id)

    def get_room_id_for_chat(self, chat_id: str) -> Optional[str]:
        """Get room ID associated with a chat ID"""
        return self.chatid_roomid_map.get(chat_id)

    def add_chat_room_mapping(self, chat_id: str, room_id: str):
        """Associate a chat ID with a room ID"""
        self.chatid_roomid_map[chat_id] = room_id
        logger.info(f"Added mapping: chat_id {chat_id} -> room_id {room_id}")

    def remove_chat_room_mapping(self, chat_id: str):
        """Remove chat ID to room ID mapping"""
        if chat_id in self.chatid_roomid_map:
            room_id = self.chatid_roomid_map.pop(chat_id)
            logger.info(f"Removed mapping: chat_id {chat_id} -> room_id {room_id}")

    async def remove_room(self, room_id: str):
        """Remove a room and cleanup its resources"""
        room = self.rooms.pop(room_id, None)
        if room:
            # Remove any chat mappings for this room
            chat_ids = [chat_id for chat_id, rid in self.chatid_roomid_map.items() if rid == room_id]
            for chat_id in chat_ids:
                self.remove_chat_room_mapping(chat_id)
            
            await room.cleanup()
            logger.info(f"Room {room_id} removed")

    # TODO: example code
    # async def save_message(self, room_id: str, message: dict):
    #     """Save a message to the database"""
    #     try:
    #         messages_collection = mongodb_client.db["messages"]
    #         await messages_collection.insert_one(message)
    #         logger.info(f"Message saved for room {room_id}")
    #     except Exception as e:
    #         logger.error(f"Error saving message for room {room_id}: {e}", exc_info=True)
