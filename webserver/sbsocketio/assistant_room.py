import logging
import socketio
from typing import Optional, Any
from abc import abstractmethod
from webserver.config import settings
from assistant.assistant_functions import AssistantFunctions
from webserver.db.chatdb.db import mongodb_client
from webserver.sbsocketio.connection_manager import ConnectionManager
from webserver.tools.stocks import get_tool_function_map as get_stocks_tool_map
from webserver.tools.perplexity import get_tool_function_map as get_perplexity_tool_map
from webserver.tools.spotify import get_tool_function_map as get_spotify_tool_map
from webserver.tools.tidal import get_tool_function_map as get_tidal_tool_map
from webserver.tools.notion import get_tool_function_map as get_notion_tool_map
from webserver.tools.google_calendar_helper import get_tool_function_map as get_gcal_tool_map
from webserver.tools.sensor_values import get_tool_function_map as get_sensor_tool_map
from webserver.tools.finance import get_tool_function_map as get_finance_tool_map
from webserver.tools.brightdata_search_tool import get_tool_function_map as get_brightdata_tool_map
from prometheus_client import Counter

logger = logging.getLogger(__name__)

ASSISTANT_FUNCTION_CALLS = Counter('assistant_function_calls', 'Total assistant function calls by name', ['function_name'])
ASSISTANT_FUNCTION_RESULTS = Counter('assistant_function_results', 'Total assistant function results by name', ['function_name'])
ASSISTANT_RESPONSES = Counter('assistant_response', 'Total assistant responses')
ASSISTANT_ERRORS = Counter('assistant_errors', 'Total assistant errors')
ASSISTANT_ROOM_EVENTS = Counter('assistant_room_events', 'Total assistant room events')
ASSISTANT_INCOMING_USER_MESSAGES = Counter('assistant_incoming_user_messages', 'Total incoming user messages')
ASSISTANT_INCOMING_MESSAGES_MODEL_ID = Counter('assistant_incoming_messages_model_id', 'Total incoming messages by model id', ['model_id'])

class AssistantRoom:
    def __init__(
        self,
        room_id: str,
        namespace: str,
        model_id: str,
        connection_manager: ConnectionManager,
        auto_execute_functions: bool = False,
        sio: socketio.AsyncServer = None,
        chat_id: Optional[str] = None,
    ):
        self.sio = sio
        self.room_id = room_id
        self.model_id = model_id
        self.namespace = namespace
        self.auto_execute_functions = auto_execute_functions

        self.connected_users: set[str] = set()
        self.connection_manager = connection_manager
        
        if chat_id:
            self.chat_id = chat_id

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

        # Get tool maps from all sources
        assistant_tool_map = self.assistant_functions.get_tool_function_map()
        stocks_tool_map = get_stocks_tool_map()
        finance_tool_map = get_finance_tool_map()
        perplexity_tool_map = get_perplexity_tool_map()
        spotify_tool_map = get_spotify_tool_map()
        tidal_tool_map = get_tidal_tool_map()
        notion_tool_map = get_notion_tool_map()
        gcal_tool_map = get_gcal_tool_map()
        sensor_tool_map = get_sensor_tool_map()
        brightdata_tool_map = get_brightdata_tool_map()
        
        # Merge all tool maps
        self.tool_map = {
            #**assistant_tool_map, 
            **stocks_tool_map,
            **finance_tool_map,
            **perplexity_tool_map,
            **spotify_tool_map,
            **tidal_tool_map,
            **notion_tool_map,
            **gcal_tool_map,
            **sensor_tool_map,
            **brightdata_tool_map
        }
        
        # Generate tool usage guide from system prompt descriptions
        self.tool_usage_guide = self._generate_tool_usage_guide()

    def _generate_tool_usage_guide(self) -> str:
        """Generate a comprehensive guide for tool usage from system prompt descriptions"""
        tool_descriptions = []
        
        for tool_name, tool_info in self.tool_map.items():
            if "system_prompt_description" in tool_info:
                tool_descriptions.append(f"- {tool_info['system_prompt_description']}")
        
        if not tool_descriptions:
            return ""
            
        guide = "Tool Usage Guide:\n"
        guide += "Here's how to effectively use the available tools:\n"
        guide += "\n".join(tool_descriptions)
        return guide

    async def _handle_send_message(self, message: dict, sid: str, model_id: str) -> None:
        logger.info(f"[ASST ROOM HANDLE SEND MESSAGE] SID: {sid}")
        ASSISTANT_INCOMING_USER_MESSAGES.inc()
        ASSISTANT_INCOMING_MESSAGES_MODEL_ID.labels(model_id=model_id).inc()

    async def _handle_function_call(self, function_name: str):
        """Handle function call and increment counter"""
        logger.info(f"[ASST ROOM HANDLE FUNCTION CALL] {function_name}")
        ASSISTANT_FUNCTION_CALLS.labels(function_name=function_name).inc()

    async def _handle_function_result(self, function_name: str):
        """Handle function result and increment counter"""
        logger.info(f"[ASST ROOM HANDLE FUNCTION RESULT] {function_name}")
        ASSISTANT_FUNCTION_RESULTS.labels(function_name=function_name).inc()

    async def _handle_response(self):
        """Handle response and increment counter"""
        logger.info(f"[ASST ROOM HANDLE RESPONSE]")
        ASSISTANT_RESPONSES.inc()

    async def _handle_room_event(self, event: Any, sid: str) -> None:
        # TODO: wrap user message broadcasting and user message storage then call handle_send_message so derived class behavior runs
        # TODO: also add self.connection_manager.get_user_id(sid) user id logic to the handle_send_message
        # TODO: also wrap message_sent return event for original sender
        logger.info(f"[ASST ROOM HANDLE ROOM EVENT] {event}")
        ASSISTANT_ROOM_EVENTS.inc()

    async def _handle_error(self, error: str):
        """Handle error and increment counter"""
        logger.error(f"[ASST ROOM HANDLE ERROR] {error}")
        ASSISTANT_ERRORS.inc()

    async def _handle_room_error(
        self,
        error: str,
        message: Optional[dict] = None,
        sender_sid: Optional[str] = None,
    ) -> None:
        """Handle errors related to user messages."""
        logger.error(f"Message error in room {self.room_id}: {error}")
        if message:
            logger.debug(f"Error message details: {message}")

        await self.broadcast(f"error {self.room_id}", sender_sid, {"error": error})

    def add_user(self, sid: str):
        """Add a user to the room"""
        self.connected_users.add(sid)
        logger.info(f"User {sid} added to room {self.room_id}")

    def remove_user(self, sid: str):
        """Remove a user from the room"""
        self.connected_users.discard(sid)
        logger.info(f"User {sid} removed from room {self.room_id}")

    async def broadcast(self, event_type: str, sid: str, data: dict) -> None:
        """Broadcast a message to all users in the room"""
        logger.info(f"[BROADCAST] Broadcasting message to all users in the room {self.room_id}")
        await self.sio.emit(
            event_type,
            data,
            room=self.room_id,
            skip_sid=sid,
            namespace=self.namespace
        )
    
    async def save_message(self, message: dict): # NEW TODO: add DBMessage type as the param, let this thing do the conversion
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
            return {"error": str(e)}
        
    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def cleanup(self):
        pass
