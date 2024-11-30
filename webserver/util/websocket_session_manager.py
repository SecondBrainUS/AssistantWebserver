from typing import Dict, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # session_id -> WebSocket
        self.user_sessions: Dict[str, Set[str]] = {}        # user_id -> set of session_ids

    async def connect(self, websocket: WebSocket, user_id: str, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = set()
        self.user_sessions[user_id].add(session_id)

    def disconnect(self, user_id: str, session_id: str):
        self.active_connections.pop(session_id, None)
        if user_id in self.user_sessions:
            self.user_sessions[user_id].discard(session_id)
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]

    async def send_personal_message(self, message: str, session_id: str):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_text(message)

    async def broadcast_to_user(self, message: str, user_id: str):
        session_ids = self.user_sessions.get(user_id, set())
        for session_id in session_ids:
            websocket = self.active_connections.get(session_id)
            if websocket:
                await websocket.send_text(message)