import logging
import asyncio
from typing import Dict, Optional
from assistant_realtime_openai import OpenAIRealTimeAPI
import json
from assistant_functions import AssistantFunctions
from webserver.config import settings

logger = logging.getLogger(__name__)

class Room:
    def __init__(self, room_id: str, api_key: str, endpoint_url: str):
        self.room_id = room_id
        self.api = OpenAIRealTimeAPI(api_key, endpoint_url)
        self.connected_users: set[str] = set()
        
        # Initialize AssistantFunctions
        self.assistant_functions = AssistantFunctions(
            openai_api_key=settings.OPENAI_API_KEY,
            notion_api_key=settings.NOTION_API_KEY,
            notion_running_list_database_id=settings.NOTION_RUNNING_LIST_DATABASE_ID,
            notion_notes_page_id=settings.NOTION_NOTES_PAGE_ID,
            gcal_credentials_path=settings.GCAL_CREDENTIALS_PATH,
            gcal_token_path=settings.GCAL_TOKEN_PATH,
            gcal_auth_method="service_account"
        )
        
    async def initialize(self):
        """Initialize the OpenAI API connection and set up event handlers"""
        try:
            # Register generic callback for all events
            self.api.set_message_callback(self._handle_openai_event)
            self.api.register_event_callback("error", self._handle_openai_error)
            
            # Register tool function handlers
            self.api.set_tool_function_map(self.assistant_functions.get_tool_function_map())
            
            # Connect to OpenAI
            await self.api.connect()
            
            # Set up the initial session with tools enabled
            await self.api.send_event("session.update", {
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": "You are a helpful assistant. Please answer clearly and concisely.",
                    "temperature": 0.8,
                    "turn_detection": None,
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": name,
                                "description": meta["description"],
                                "parameters": meta["parameters"]
                            }
                        }
                        for name, meta in self.assistant_functions.get_tool_function_map().items()
                    ]
                }
            })
            
            logger.info(f"Room {self.room_id} initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize room {self.room_id}: {e}")
            return False

    async def _handle_openai_event(self, message):
        """Handle all messages from OpenAI and broadcast to room"""
        try:
            # Parse the raw message
            event = json.loads(message)
            event_type = event.get('type')
            
            logger.debug(f"Received OpenAI event in room {self.room_id}: {event_type}")
            
            # This will be caught by the namespace to broadcast
            return {
                "event_type": event_type,
                "data": event,
                "room_id": self.room_id
            }
        except Exception as e:
            logger.error(f"Error handling OpenAI event in room {self.room_id}: {e}")

    async def _handle_openai_error(self, error: str, event: Optional[dict] = None):
        """Handle errors from OpenAI"""
        logger.error(f"OpenAI error in room {self.room_id}: {error}")
        if event:
            logger.debug(f"Error event details: {event}")

    async def send_message(self, message_data: dict):
        """Send a message event to OpenAI"""
        logger.debug(f"[CHECK CHECK] Sending message to OpenAI in room {self.room_id}: {message_data}")
        try:
            type = message_data.get('type')
            data = message_data.get('data')
            
            if not type:
                raise ValueError("Message must include type")
            
            if data is None:
                logger.debug(f"No 'data' field found in message, using message properties as payload")
                payload = message_data.copy()
                payload.pop('type', None)
                data = payload if payload else {}
            
            logger.debug(f"Sending event type '{type}' with data: {data}")
            await self.api.send_event(type, data)
            
        except Exception as e:
            logger.error(f"Error sending message to OpenAI in room {self.room_id}: {e}")
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
    def __init__(self, api_key: str, endpoint_url: str):
        self.rooms: Dict[str, Room] = {}
        self.api_key = api_key
        self.endpoint_url = endpoint_url

    async def create_room(self, room_id: str) -> bool:
        """Create a new room with OpenAI API instance"""
        if room_id in self.rooms:
            logger.warning(f"Room {room_id} already exists")
            return False

        room = Room(room_id, self.api_key, self.endpoint_url)
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