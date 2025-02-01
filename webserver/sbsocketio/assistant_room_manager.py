import logging
import socketio
from typing import Dict, Optional
from webserver.sbsocketio.connection_manager import ConnectionManager
from webserver.sbsocketio.assistant_room import AssistantRoom
from webserver.sbsocketio.assistant_room_openai_realtime import OpenAiRealTimeRoom
from webserver.sbsocketio.assistant_room_aisuite import AiSuiteRoom
logger = logging.getLogger(__name__)

class AssistantRoomManager:
    def __init__(self, connection_manager: ConnectionManager, sio: socketio.AsyncServer):
        self.sio: socketio.AsyncServer = sio
        self.rooms: Dict[str, AssistantRoom] = {}
        self.chatid_roomid_map: Dict[str, str] = {}
        self.connection_manager: ConnectionManager = connection_manager

    async def create_room(self, room_id: str, namespace: str, model_api_source: str, model_id: str, chat_id: str) -> bool:
        """Create a new room with OpenAI API instance"""
        if room_id in self.rooms:
            logger.warning(f"Room {room_id} already exists")
            return False
        
        room_types = {
            "openai_realtime": OpenAiRealTimeRoom,
            "aisuite": AiSuiteRoom,
        }
        room_class = room_types.get(model_api_source.lower())
        if not room_class:
            raise ValueError(f"Unsupported API source: {model_api_source}")
            
        room: AssistantRoom = room_class(
            room_id=room_id, 
            namespace=namespace,
            model_id=model_id,
            connection_manager=self.connection_manager,
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
