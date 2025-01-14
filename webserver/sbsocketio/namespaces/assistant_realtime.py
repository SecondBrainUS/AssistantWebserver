import logging
import traceback
import uuid
from typing import Optional
from http.cookies import SimpleCookie
from webserver.config import settings
from .base import BaseNamespace
from ..room_manager import AssistantRoomManager
from jose import jwt
import json
from datetime import datetime
from webserver.db.memcache.connection import get_memcache_client
from webserver.db.assistantdb.connection import get_db
from webserver.db.assistantdb.model import UserSession, User
from webserver.db.chatdb.connection import get_chats_collection, get_messages_collection
from webserver.db.chatdb.db import mongodb_client

logger = logging.getLogger(__name__)

class AssistantRealtimeNamespace(BaseNamespace):
    def __init__(self, sio, connection_manager):
        super().__init__(sio, connection_manager)
        self.room_manager = AssistantRoomManager(
            api_key=settings.OPENAI_API_KEY,
            endpoint_url=settings.OPENAI_REALTIME_ENDPOINT_URL,
            connection_manager=self.connection_manager,
            sio=self.sio
        )
        self.memcache_client = None
        self.db = None
        

    def get_namespace(self) -> str:
        return '/assistant/realtime'

    async def initialize_connections(self):
        """Lazy initialization of database connections"""
        if not self.memcache_client:
            self.memcache_client = await get_memcache_client()
        if not self.db:
            self.db = next(get_db())

    async def verify_access_token(self, access_token: str):
        """Verify JWT access token"""
        try:
            payload = jwt.decode(
                access_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            if payload.get("token_type") != "access":
                return None
            return payload
        except:
            return None

    async def get_session_and_user(self, session_id: str):
        """Get session and user data from cache or database"""
        # Check cache first for session
        cached_session = await self.memcache_client.get(f"session:{session_id}".encode())
        if cached_session:
            session_dict = json.loads(cached_session.decode())
            session_data = {
                **session_dict,
                "session_expires": datetime.fromisoformat(session_dict["session_expires"]),
                "access_token_expires": datetime.fromisoformat(session_dict["access_token_expires"]),
                "refresh_token_expires": datetime.fromisoformat(session_dict["refresh_token_expires"]),
                "created": datetime.fromisoformat(session_dict["created"]),
                "updated": datetime.fromisoformat(session_dict["updated"]),
            }
            
            # Check cache for user
            cached_user = await self.memcache_client.get(f"user:{session_dict['user_id']}".encode())
            if cached_user:
                user_data = json.loads(cached_user.decode())
                return session_data, user_data

        # If not in cache, check database
        db_session = self.db.query(UserSession).filter(UserSession.session_id == session_id).first()
        if not db_session:
            return None, None

        db_user = self.db.query(User).filter(User.user_id == db_session.user_id).first()
        if not db_user:
            return None, None

        session_data = db_session.to_dict()
        user_data = db_user.to_dict()
        
        return session_data, user_data

    def register_handlers(self):
        @self.sio.on('connect', namespace=self.namespace)
        async def connect(sid: str, environ: dict, auth: dict):
            try:
                await self.initialize_connections()
                
                # Get cookies
                cookie = environ.get('HTTP_COOKIE', '')
                parsed_cookie = SimpleCookie(cookie)
                parsed_cookies = {key: morsel.value for key, morsel in parsed_cookie.items()}
                
                access_token = parsed_cookies.get('access_token')
                session_id = parsed_cookies.get('session_id')

                # Verify access token
                jwt_payload = await self.verify_access_token(access_token)
                if not jwt_payload:
                    logger.warning(f"Invalid access token for SID {sid}")
                    await self.sio.disconnect(sid)
                    return

                # Get session and user data
                session_data, user_data = await self.get_session_and_user(session_id)
                if not session_data or not user_data:
                    logger.warning(f"Invalid session/user data for SID {sid}")
                    await self.sio.disconnect(sid)
                    return

                # Store user and session data in connection manager
                self.connection_manager.add_connection(user_data['user_id'], sid, {
                    'user': user_data,
                    'session': session_data
                })

                logger.info(f"User {user_data['user_id']} connected with SID {sid}")

            except Exception as e:
                logger.error(f"Error in connect handler: {e}", exc_info=True)
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
            chat_id = data.get('chat_id')
            model = data.get('model')
            room_uuid = str(uuid.uuid4())
            room_id = f"room_{room_uuid}"

            success = await self.room_manager.create_room(room_id, self.namespace, chat_id, model)
            if success:
                logger.info(f"Created assistant room: {room_id}")
                await self.sio.emit('room_created', 
                    {'room_id': room_id, 'chat_id': chat_id, 'model': model}, 
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

        @self.sio.on('find_chat', namespace=self.namespace)
        async def find_chat(sid: str, data: dict):
            logger.info(f"[FIND CHAT] Received find_chat request from SID {sid}: {data}")
            chat_id = data.get('chat_id')
            if not chat_id:
                logger.warning(f"Invalid find_chat attempt from SID {sid}: missing chat_id")
                return

            room_id = self.room_manager.get_room_id_for_chat(chat_id)
            if not room_id:
                logger.info(f"[FIND CHAT] Room not found for chat {chat_id}")
                await self.sio.emit(f'room_not_found {chat_id}', {'room_id': room_id, 'chat_id': chat_id}, room=sid, namespace=self.namespace)
                return

            logger.info(f"[FIND CHAT] Room found for chat {chat_id}: {room_id}")
            await self.sio.emit(f'room_found {chat_id}', {'room_id': room_id, 'chat_id': chat_id}, room=sid, namespace=self.namespace)

        @self.sio.on('send_message', namespace=self.namespace)
        async def send_assistant_message(sid: str, data: dict):
            try:
                logger.debug(f"[SEND MESSAGE] Starting with data: {data}")
                room_id = data.get('room_id')
                message = data.get('message')
                model = data.get('model')

                
                if not (room_id and message):
                    logger.warning(f"Invalid message data from SID {sid}: {data}")
                    return

                logger.debug(f"[SEND MESSAGE] Got room_id and message, getting room")
                room = self.room_manager.get_room(room_id)
                if not room:
                    logger.warning(f"[SEND MESSAGE] Message sent to non-existent room {room_id}")
                    await self.sio.emit('room_error', 
                        {'error': 'Room does not exist'}, 
                        room=sid, 
                        namespace=self.namespace
                    )
                    return

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
                    await room.send_message(message, sid, model)
                    
                except Exception as e:
                    logger.error(f"Error in send_assistant_message: {e}")
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    await self.sio.emit('room_error', 
                        {'error': f'Failed to process message: {str(e)}'}, 
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

    def _setup_room_message_handler(self, room) -> None:
        """Set up message handling for a room."""
        room.set_message_callback(self._broadcast_room_message)

    async def _send_message_error(self, sid: str, error_data: dict):
        await self.sio.emit('message_error', error_data, room=sid, namespace=self.namespace)
