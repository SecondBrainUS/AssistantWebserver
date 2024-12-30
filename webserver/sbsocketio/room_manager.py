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

logger = logging.getLogger(__name__)


async def save_message(message: dict):
    """Save a message to the database"""
    message_id = message["message_id"]
    try:
        messages_collection = mongodb_client.db["messages"]
        await messages_collection.insert_one(message)
        logger.info(f"Message saved for message_id {message_id}")
        return {"success": True, "message_id": message_id}
    except Exception as e:
        logger.error(
            f"Error saving message for message_id {message_id}: {e}", exc_info=True
        )
        return {"error": e}


async def save_chat(chat: dict):
    """Save a chat to the database"""
    chat_id = chat["chat_id"]
    try:
        chats_collection = mongodb_client.db["chats"]
        await chats_collection.insert_one(chat)
        logger.info(f"Chat saved for chat_id {chat_id}")
        return {"success": True, "chat_id": chat_id}
    except Exception as e:
        logger.error(f"Error saving chat for chat_id {chat_id}: {e}", exc_info=True)
        return {"error": e}


class Room:
    def __init__(
        self,
        room_id: str,
        api_key: str,
        endpoint_url: str,
        connection_manager,
        auto_execute_functions: bool = False,
    ):
        self.room_id = room_id
        self.api = OpenAIRealTimeAPI(api_key, endpoint_url)
        self.api.set_auto_execute_functions(auto_execute_functions)
        self.connected_users: set[str] = set()
        self.message_count = 0
        self.connection_manager = connection_manager

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

            # Special handling for tool call results and summaries
            # if event_type == "tool_call.result":
            #     logger.debug(f"Tool call result received in room {self.room_id}")
            #     # Tool results are handled internally by OpenAI API
            #     return

            # Broadcast the event to room members
            if self._message_callback:
                await self._message_callback(
                    {"event_type": event_type, "data": event, "room_id": self.room_id}
                )
            else:
                logger.warning(f"No message callback set for room {self.room_id}")

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
        if event:
            logger.debug(f"Error event details: {event}")

        # Broadcast error to room members if callback is set
        if self._message_callback:
            await self._message_callback(
                {
                    "event_type": "error",
                    "data": {"error": error, "event": event},
                    "room_id": self.room_id,
                }
            )

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

            # If not a user conversation message, just send it to the API
            if message.get("type") != "conversation.item.create":
                logger.info(f"[SEND MESSAGE] Not a conversation.item.create")
                await self.api.send_event(
                    event_type=message["type"], data=message.get("data", {})
                )
                return

            logger.info(f"[SEND MESSAGE] ", message)

            chat_id = message.get("chat_id")
            if not chat_id:
                # TODO: add background task to name the chat by LLM, update the chat with the name by ID
                chat_id = str(uuid.uuid4())
                chat = {
                    "chat_id": chat_id,
                    "user_id": userid,
                    "created_timestamp": datetime.now(),
                }

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
                    "chat_id": chat_id,
                    "user_id": userid,
                    "model": model,
                    "created_timestamp": created_timestamp,
                    "role": role,
                    "content": chat_message_content,
                    "modality": modality,
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
