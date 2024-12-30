import logging
import asyncio
import json
import uuid
from typing import Dict, Optional
from datetime import datetime
from assistant_realtime_openai import OpenAIRealTimeAPI
from assistant_functions import AssistantFunctions
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
        # Convert UUIDs to Binary format
        message["message_id"] = uuid_to_binary(message_id)
        message["chat_id"] = uuid_to_binary(message["chat_id"])
        
        messages_collection = mongodb_client.db["messages"]
        await messages_collection.insert_one(message)
        logger.info(f"Message saved for message_id {message_id}")
        return {"success": True, "message_id": str(ensure_uuid(message_id))}
    except Exception as e:
        logger.error(f"Error saving message for message_id {message_id}: {e}", exc_info=True)
        return {"error": e}


async def save_chat(chat: dict):
    """Save a chat to the database"""
    chat_id = chat["chat_id"]
    try:
        # Convert the chat_id to Binary format
        chat["chat_id"] = uuid_to_binary(chat_id)
        
        chats_collection = mongodb_client.db["chats"]
        await chats_collection.insert_one(chat)
        logger.info(f"Chat saved for chat_id {chat_id}")
        return {"success": True, "chat_id": str(ensure_uuid(chat_id))}
    except Exception as e:
        logger.error(f"Error saving chat for chat_id {chat_id}: {e}", exc_info=True)
        return {"error": e}


class Room:
    def __init__(
        self,
        room_id: str,
        api_key: str,
        endpoint_url: str,
        connection_manager: ConnectionManager,
        auto_execute_functions: bool = False,
    ):
        self.room_id = room_id
        self.api = OpenAIRealTimeAPI(api_key, endpoint_url)
        self.api.set_auto_execute_functions(auto_execute_functions)
        self.connected_users: set[str] = set()
        self.message_count = 0
        self.connection_manager = connection_manager
        self.chat_id: Optional[str] = None

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

        # Initialize event system
        self._event_handlers = {
            "message": [],
            "error": [],
            "chat_created": [],
            "function_call": [],
            "response_complete": []
        }

    def add_event_handler(self, event_type: str, handler: callable) -> None:
        """Register a new event handler for the specified event type"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def _dispatch_event(self, event_type: str, data: dict) -> None:
        """Dispatch an event to all registered handlers"""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                await handler(data)

    async def initialize(self):
        """Initialize the OpenAI API connection and set up event handlers"""
        try:
            # Register generic callback for all events
            self.api.set_message_callback(self._handle_openai_event)
            self.api.register_event_callback("error", self._handle_openai_error)

            # Get tool function map
            tool_map = self.assistant_functions.get_tool_function_map()

            # Register tool functions with API
            self.api.set_tool_function_map(tool_map)

            # Connect to OpenAI
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

    async def _handle_openai_event(self, message: str) -> None:
        """Handle all messages from OpenAI and broadcast to room."""
        try:
            # Parse the raw message
            event = json.loads(message)
            event_type = event.get("type")

            logger.debug(f"Received OpenAI event in room {self.room_id}: {event_type}")

            # Dispatch the raw event to handlers
            await self._dispatch_event("message", {
                "event_type": event_type,
                "data": event,
                "room_id": self.room_id
            })

            # Process response.done events
            if event_type == "response.done":
                response = event.get('response')
                if not response:
                    logger.error(f"No response found in event {event}")
                    return
                    
                output = response.get('output')
                if not output:
                    logger.error(f"No output found in response {response}")
                    return

                response_message = None
                if len(output) > 1:
                    logger.warning(f"[OPENAI EVENT] [RESPONSE.DONE] Multiple outputs found in response {response}")
                    response_message = output[0]
                elif len(output) == 1:
                    response_message = output[0]
                else:
                    logger.error(f"[OPENAI EVENT] [RESPONSE.DONE] No output found in response {response}")
                    return

                if response_message.get('type') == "message":
                    # Process text message
                    await self._handle_text_message(response_message, event)
                    await self._dispatch_event("response_complete", {
                        "message": response_message,
                        "usage": event.get('usage')
                    })

                elif response_message.get('type') == "function_call":
                    # Process function call
                    await self._handle_function_call(response_message, event)
                    await self._dispatch_event("function_call", {
                        "function_call": response_message,
                        "usage": event.get('usage')
                    })

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing OpenAI event in room {self.room_id}: {e}")
            await self._dispatch_event("error", {"error": str(e)})
        except Exception as e:
            logger.error(
                f"Error handling OpenAI event in room {self.room_id}: {e}",
                exc_info=True,
            )
            await self._dispatch_event("error", {"error": str(e)})

    async def _handle_text_message(self, response_message: dict, event: dict):
        """Handle text message responses"""
        response_message_content = response_message.get('content')
        if not response_message_content:
            logger.error(f"No content found in response message {response_message}")
            return
            
        response_message_text = response_message_content.get('text')
        response_message_type = response_message.get('type')

        messageid = str(uuid.uuid4())
        created_timestamp = datetime.now()
        role = response_message.get('role')
        model = "OpenAI Real Time GPT-4"
        usage = event.get('usage')
        
        await save_message({ 
            "message_id": messageid,
            "chat_id": self.chat_id,
            "model": model,
            "created_timestamp": created_timestamp,
            "role": role,
            "content": response_message_text,
            "modality": response_message_type,
            "type": "message",
            "usage": usage,
        })

    async def _handle_function_call(self, response_message: dict, event: dict):
        """Handle function call responses"""
        messageid = str(uuid.uuid4())
        created_timestamp = datetime.now()
        role = "system"
        model = "OpenAI Real Time GPT-4"
        usage = event.get('usage')
        
        await save_message({ 
            "message_id": messageid,
            "chat_id": self.chat_id,
            "model": model,
            "created_timestamp": created_timestamp,
            "role": role,
            "type": "function_call",
            "usage": usage,
            "name": response_message.get('name'),
            "arguments": response_message.get('arguments'),
            "callid": response_message.get('callid'),
        })

    async def _handle_openai_error(self, error: str, event: Optional[dict] = None) -> None:
        """Handle errors from OpenAI."""
        logger.error(f"OpenAI error in room {self.room_id}: {error}")
        if event:
            logger.debug(f"Error event details: {event}")

        await self._dispatch_event("error", {
            "error": error,
            "event": event,
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
            # Get user data from connection manager if needed
            logger.info(f"[SEND MESSAGE] Getting user data for socket {sid}")
            userid = self.connection_manager.get_user_id(sid)
            if not userid:
                logger.error(f"No user data found for user {userid}")
                return

            logger.info(f"[SEND MESSAGE] Raw chat message: {message}")

            # Handle non-conversation messages differently
            if message.get("type") not in ["message", "conversation.item.create"]:
                logger.info(f"[SEND MESSAGE] Special event type: {message.get('type')}")
                await self.api.send_event(
                    event_type=message["type"], 
                    data=message.get("data", {})
                )
                return

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
                    # Emit chat_created event
                    await self._dispatch_event("chat_created", {
                        "chat_id": chat_id,
                        "room_id": self.room_id
                    })
                else:
                    logger.error(f"[SEND MESSAGE] Error saving chat: {save_chat_result.get('error')}")
                    return

            self.message_count += 1
            # Extract auto_execute setting from message if present
            auto_execute = message.get("auto_execute_functions", False)
            self.api.set_auto_execute_functions(auto_execute)

            # Get the content based on message type
            content = None
            if message.get("type") == "message":
                content = message.get("content", [])
            else:  # conversation.item.create
                item = message.get("data", {}).get("item", {})
                content = item.get("content", [])

            # Verify content
            if not content or not isinstance(content, list):
                logger.error(f"[SEND MESSAGE] Invalid content format: {message}")
                await self._dispatch_event("error", {
                    "error": "Invalid content format",
                    "room_id": self.room_id
                })
                return

            content_item = content[0]
            if content_item["type"] != "input_text":
                logger.error(
                    f"[SEND MESSAGE] Message is not an input_text: {content_item['type']}"
                )
                await self._dispatch_event("error", {
                    "error": "Invalid content type",
                    "room_id": self.room_id
                })
                return

            chat_message_content = content_item["text"]
            role = message.get("role", "user")
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

            # Send the actual message to OpenAI
            logger.info(f"[SEND MESSAGE] Sending message to OpenAI API")
            if message.get("type") == "message":
                # Convert to OpenAI format if needed
                openai_message = {
                    "type": "conversation.item.create",
                    "data": {
                        "item": {
                            "role": role,
                            "content": content,
                            "type": "message"
                        }
                    }
                }
                await self.api.send_event(
                    event_type="conversation.item.create",
                    data=openai_message.get("data", {})
                )
            else:
                # Already in OpenAI format
                await self.api.send_event(
                    event_type=message["type"],
                    data=message.get("data", {})
                )

        except Exception as e:
            logger.error(
                f"Error sending message in room {self.room_id}: {e}", exc_info=True
            )
            await self._dispatch_event("error", {
                "error": str(e),
                "room_id": self.room_id
            })
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


class RoomManager:
    def __init__(self, api_key: str, endpoint_url: str, connection_manager):
        self.rooms: Dict[str, Room] = {}
        self.api_key = api_key
        self.endpoint_url = endpoint_url
        self.connection_manager = connection_manager

    async def create_room(self, room_id: str) -> bool:
        """Create a new room with OpenAI API instance"""
        if room_id in self.rooms:
            logger.warning(f"Room {room_id} already exists")
            return False

        room = Room(room_id, self.api_key, self.endpoint_url, self.connection_manager)
        success = await room.initialize()

        if success:
            self.rooms[room_id] = room
            logger.info(f"Room {room_id} created successfully")
            return True
        else:
            logger.error(f"Failed to create room {room_id}")
            return False

    def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by ID"""
        return self.rooms.get(room_id)

    async def remove_room(self, room_id: str):
        """Remove a room and cleanup its resources"""
        room = self.rooms.pop(room_id, None)
        if room:
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
