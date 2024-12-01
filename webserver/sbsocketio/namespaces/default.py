import logging
from .base import BaseNamespace

logger = logging.getLogger(__name__)

class DefaultNamespace(BaseNamespace):
    def get_namespace(self) -> str:
        return '/'  # Default namespace

    def register_handlers(self):
        @self.sio.event
        async def connect(sid: str, environ: dict, auth: dict):
            logger.info(f"Connect attempt - SID: {sid}")
            logger.info(f"Auth data: {auth}")
            logger.info(f"Environment: {environ}")
            logger.info(f"Client connected: {sid}")
            
            user_id = auth.get('user_id') if auth else None
            if user_id:
                self.connection_manager.add_connection(user_id, sid)
                logger.info(f"User {user_id} connected with SID {sid}")
            else:
                logger.warning(f"No user_id provided in auth for SID {sid}")
                await self.sio.disconnect(sid)

        @self.sio.event
        async def disconnect(sid: str):
            logger.info(f"Client disconnected: {sid}")
            user_id = self.connection_manager.remove_connection(sid)
            if user_id:
                logger.info(f"User {user_id} disconnected")
            else:
                logger.warning(f"No user_id found for SID {sid} on disconnect")

        @self.sio.event
        async def join_room(sid: str, data: dict):
            """Handle room joining with room name from data dict"""
            room = data.get('room')
            if room:
                await self.sio.enter_room(sid, room)
                logger.info(f"SID {sid} joined room {room}")
                await self.sio.emit('room_joined', {'room': room}, room=sid)
            else:
                logger.warning(f"No room specified for SID {sid} to join")

        @self.sio.event
        async def leave_room(sid: str, data: dict):
            room = data.get('room')
            if room:
                await self.sio.leave_room(sid, room)
                logger.info(f"SID {sid} left room {room}")
                await self.sio.emit('room_left', {'room': room}, room=sid)
            else:
                logger.warning(f"No room specified for SID {sid} to leave")

        @self.sio.event
        async def send_message(sid: str, data: dict):
            """Handle message sending with standardized data format"""
            room = data.get('room')
            message = data.get('message')
            if room and message:
                logger.info(f"Broadcasting message in room {room} from {sid}")
                await self.sio.emit('receive_message', {
                    'room': room,
                    'message': message
                }, room=room)
            else:
                logger.warning(f"Invalid message data from SID {sid}: {data}")
