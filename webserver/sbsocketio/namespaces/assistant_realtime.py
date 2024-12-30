import logging
import traceback
from typing import Optional
from http.cookies import SimpleCookie
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
        @self.sio.on('connect', namespace=self.namespace)
        async def connect(sid: str, environ: dict, auth: dict):
            #logger.info(f"Connect attempt - SID: {sid}")
            #logger.info(f"Auth data: {auth}")
            #logger.info(f"Environment: {environ}")
            #logger.info(f"Client connected: {sid}")

            cookie = environ.get('HTTP_COOKIE', '')
            parsed_cookie = SimpleCookie(cookie)
            parsed_cookies = {key: morsel.value for key, morsel in parsed_cookie.items()}
            access_token = parsed_cookies.get('access_token')
            session_id = parsed_cookies.get('session_id')
            logger.info(f"Access token: {access_token}")
            logger.info(f"Session ID: {session_id}")
            
            user_id = auth.get('user_id') if auth else None
            if user_id:
                self.connection_manager.add_connection(user_id, sid)
                logger.info(f"User {user_id} connected with SID {sid}")
            else:
                logger.warning(f"No user_id provided in auth for SID {sid}")
                await self.sio.disconnect(sid)

        @self.sio.on('disconnect', namespace=self.namespace)
        async def disconnect(sid: str):
            logger.info(f"Client disconnected: {sid}")
            user_id = self.connection_manager.remove_connection(sid)
            if user_id:
                logger.info(f"User {user_id} disconnected")
            else:
                logger.warning(f"No user_id found for SID {sid} on disconnect")

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
            try:
                logger.debug(f"[SEND MESSAGE] Starting with data: {data}")
                room_id = data.get('room_id')
                message = data.get('message')
                userid = data.get('userid')
                model = data.get('model')

                
                if not (room_id and message):
                    logger.warning(f"Invalid message data from SID {sid}: {data}")
                    return

                logger.debug(f"[SEND MESSAGE] Got room_id and message, getting room")
                room = self.room_manager.get_room(room_id)
                
                if room:
                    logger.debug(f"[SEND MESSAGE] Found room, setting up response handler")
                    try:
                        # Broadcast the user's message
                        await self.sio.emit('receive_message', {
                            'room_id': room_id,
                            'message': message,
                            'type': 'user'
                        }, room=room_id, skip_sid=sid, namespace=self.namespace)

                        logger.debug(f"[SEND MESSAGE] Broadcast user message, setting up OpenAI callback")
                        
                        # Set up callback for responses
                        async def handle_openai_response(response_data):
                            # logger.debug(f"[OPENAI CALLBACK] Received response: {response_data}")
                            await self.sio.emit('receive_message', {
                                'room_id': room_id,
                                'message': response_data,
                                'type': 'assistant'
                            }, room=room_id, namespace=self.namespace)

                        logger.debug(f"[SEND MESSAGE] Setting message callback")
                        room.api.set_message_callback(handle_openai_response)
                        
                        logger.debug(f"[SEND MESSAGE] Sending message to room")
                        await room.send_message(message, userid, model)
                        
                    except Exception as e:
                        logger.error(f"Error in send_assistant_message: {e}")
                        logger.error(f"Full traceback: {traceback.format_exc()}")
                        await self.sio.emit('room_error', 
                            {'error': f'Failed to process message: {str(e)}'}, 
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
            except Exception as e:
                logger.error(f"Top-level error in send_assistant_message: {e}")
                logger.error(f"Full traceback: {traceback.format_exc()}")
                await self.sio.emit('room_error', 
                    {'error': f'Failed to process message: {str(e)}'}, 
                    room=sid, 
                    namespace=self.namespace
                )

    async def _broadcast_room_message(self, message_data: dict) -> None:
        """Broadcast a message to all members of a room."""
        try:
            room_id = message_data.get("room_id")
            if not room_id:
                logger.error("No room_id in message data")
                return

            await self.sio.emit(
                'receive_message',
                message_data,
                room=room_id,
                namespace=self.namespace
            )
        except Exception as e:
            logger.error(f"Error broadcasting room message: {e}", exc_info=True)

    @staticmethod
    def _setup_room_message_handler(room) -> None:
        """Set up message handling for a room."""
        room.set_message_callback(self._broadcast_room_message)

    async def create_assistant_room(self, sid: str, data: dict):
        """Create a new assistant room."""
        room_id = data.get('room_id')
        if not room_id:
            logger.warning(f"Invalid room creation attempt from SID {sid}: missing room_id")
            return

        try:
            success = await self.room_manager.create_room(room_id)
            if success:
                # Set up message handling for the new room
                room = self.room_manager.get_room(room_id)
                self._setup_room_message_handler(room)
                
                # Set up message error handling for the new room
                room.set_message_error_callback(lambda error_data: self._send_message_error(sid, error_data))
                
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
        except Exception as e:
            logger.error(f"Error creating room: {e}", exc_info=True)
            await self.sio.emit('room_error', 
                {'error': f'Failed to create room: {str(e)}'}, 
                room=sid, 
                namespace=self.namespace
            )

    async def _send_message_error(self, sid: str, error_data: dict):
        await self.sio.emit('message_error', error_data, room=sid, namespace=self.namespace)
