import logging
from typing import Optional
from webserver.config import settings
from .base import BaseNamespace
from ..room_manager import RoomManager

logger = logging.getLogger(__name__)

class AssistantRealtimeNamespace(BaseNamespace):
    def __init__(self, sio, connection_manager):
        self.room_manager = RoomManager(
            api_key=settings.OPENAI_API_KEY,  # Load from config
            endpoint_url=settings.OPENAI_REALTIME_ENDPOINT_URL  # Load from config
        )
        super().__init__(sio, connection_manager)

    def get_namespace(self) -> str:
        return '/assistant/realtime'

    def register_handlers(self):
        @self.sio.on('create_room', namespace=self.namespace)
        async def create_assistant_room(sid: str, data: dict):
            room_id = data.get('room_id')
            if not room_id:
                logger.warning(f"Invalid room creation attempt from SID {sid}: missing room_id")
                return

            success = await self.room_manager.create_room(room_id)
            if success:
                logger.info(f"Created assistant room: {room_id}")
                await self.sio.emit('room_created', 
                    {'room_id': room_id}, 
                    room=sid, 
                    namespace=self.namespace
                )
            else:
                logger.error(f"Failed to create room {room_id}")
                await self.sio.emit('room_error', 
                    {'error': 'Failed to create room'}, 
                    room=sid, 
                    namespace=self.namespace
                )

        @self.sio.on('join_room', namespace=self.namespace)
        async def join_assistant_room(sid: str, data: dict):
            room_id = data.get('room_id')
            if not room_id:
                logger.warning(f"Invalid room join attempt from SID {sid}: missing room_id")
                return

            room = self.room_manager.get_room(room_id)
            if room:
                await self.sio.enter_room(sid, room_id, namespace=self.namespace)
                room.add_user(sid)
                logger.info(f"SID {sid} joined assistant room {room_id}")
                await self.sio.emit('room_joined', 
                    {'room_id': room_id}, 
                    room=sid, 
                    namespace=self.namespace
                )
            else:
                logger.warning(f"Attempt to join non-existent room {room_id}")
                await self.sio.emit('room_error', 
                    {'error': 'Room does not exist'}, 
                    room=sid, 
                    namespace=self.namespace
                )

        @self.sio.on('leave_room', namespace=self.namespace)
        async def leave_assistant_room(sid: str, data: dict):
            room_id = data.get('room_id')
            if not room_id:
                logger.warning(f"Invalid room leave attempt from SID {sid}: missing room_id")
                return

            room = self.room_manager.get_room(room_id)
            if room:
                await self.sio.leave_room(sid, room_id, namespace=self.namespace)
                room.remove_user(sid)
                logger.info(f"SID {sid} left assistant room {room_id}")
                
                # If room is empty, clean it up
                if not room.connected_users:
                    await self.room_manager.remove_room(room_id)
                
                await self.sio.emit('room_left', 
                    {'room_id': room_id}, 
                    room=sid, 
                    namespace=self.namespace
                )

        @self.sio.on('send_message', namespace=self.namespace)
        async def send_assistant_message(sid: str, data: dict):
            room_id = data.get('room_id')
            message = data.get('message')
            logger.debug(f"[CHECK CHECK] Sending message to room {room_id}: {message}")
            if not (room_id and message):
                logger.warning(f"Invalid message data from SID {sid}: {data}")
                return

            room = self.room_manager.get_room(room_id)
            
			# Add a translation layer here, message types sent to the room vs OpenAI
            

            if room:
                try:
                    # Broadcast the user's message to everyone else in the room except the sender
                    await self.sio.emit('receive_message', {
                        'room_id': room_id,
                        'message': message,
                        'type': 'user'
                    }, room=room_id, skip_sid=sid, namespace=self.namespace)

                    # Send message to OpenAI and set up callback for responses
                    async def handle_openai_response(response_data):
                        # Broadcast OpenAI's response to everyone in the room
                        await self.sio.emit('receive_message', {
                            'room_id': room_id,
                            'message': response_data,
                            'type': 'assistant'
                        }, room=room_id, namespace=self.namespace)

                    # Register the callback for this room's responses
                    room.api.set_message_callback(handle_openai_response)
                    
                    # Send the message to OpenAI
                    await room.send_message(message)
                    
                except Exception as e:
                    logger.error(f"Error processing message in room {room_id}: {e}")
                    await self.sio.emit('room_error', 
                        {'error': 'Failed to process message'}, 
                        room=sid, 
                        namespace=self.namespace
                    )
            else:
                logger.warning(f"Message sent to non-existent room {room_id}")
                await self.sio.emit('room_error', 
                    {'error': 'Room does not exist'}, 
                    room=sid, 
                    namespace=self.namespace
                )
