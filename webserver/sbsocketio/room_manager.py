import logging
import asyncio
from typing import Dict, Optional
from assistant_realtime_openai import OpenAIRealTimeAPI
import json
from assistant_functions import AssistantFunctions
from webserver.config import settings

logger = logging.getLogger(__name__)

class Room:
    def __init__(self, room_id: str, api_key: str, endpoint_url: str, auto_execute_functions: bool = False):
        self.room_id = room_id
        self.api = OpenAIRealTimeAPI(api_key, endpoint_url)
        self.api.set_auto_execute_functions(auto_execute_functions)
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
        
        # Store message callback for broadcasting
        self._message_callback = None
        
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
                tool = {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": meta["description"],
                        "parameters": meta["parameters"]
                    }
                }
                tools.append(tool)
            
            # Set up the initial session with tools enabled
            await self.api.send_event("session.update", {
                "session": {
                    "modalities": ["text"],
                    "instructions": "You are a helpful assistant. Please answer clearly and concisely.",
                    "temperature": 0.8,
                    "tools": tools  # Now properly formatted
                }
            })
            
            logger.info(f"Room {self.room_id} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing room {self.room_id}: {e}", exc_info=True)
            return False

    def set_message_callback(self, callback: callable) -> None:
        """Set the callback for broadcasting messages to room members."""
        self._message_callback = callback

    async def _handle_openai_event(self, message: str) -> None:
        """Handle all messages from OpenAI and broadcast to room."""
        try:
            # Parse the raw message
            event = json.loads(message)
            event_type = event.get('type')
            
            logger.debug(f"Received OpenAI event in room {self.room_id}: {event_type}")
            
            # Special handling for tool call results and summaries
            if event_type == "tool_call.result":
                logger.debug(f"Tool call result received in room {self.room_id}")
                # Tool results are handled internally by OpenAI API
                return
                
            # Broadcast the event to room members
            if self._message_callback:
                await self._message_callback({
                    "event_type": event_type,
                    "data": event,
                    "room_id": self.room_id
                })
            else:
                logger.warning(f"No message callback set for room {self.room_id}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing OpenAI event in room {self.room_id}: {e}")
        except Exception as e:
            logger.error(f"Error handling OpenAI event in room {self.room_id}: {e}", exc_info=True)

    async def _handle_openai_error(self, error: str, event: Optional[dict] = None) -> None:
        """Handle errors from OpenAI."""
        logger.error(f"OpenAI error in room {self.room_id}: {error}")
        if event:
            logger.debug(f"Error event details: {event}")
        
        # Broadcast error to room members if callback is set
        if self._message_callback:
            await self._message_callback({
                "event_type": "error",
                "data": {"error": error, "event": event},
                "room_id": self.room_id
            })

    async def send_message(self, message: dict) -> None:
        """Send a message to the OpenAI API."""
        try:
            # Extract auto_execute setting from message if present
            auto_execute = message.get("auto_execute_functions", False)
            self.api.set_auto_execute_functions(auto_execute)
            
            # Send the actual message
            await self.api.send_event(
                event_type=message["type"],
                data=message.get("data", {})
            )
        except Exception as e:
            logger.error(f"Error sending message in room {self.room_id}: {e}", exc_info=True)
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