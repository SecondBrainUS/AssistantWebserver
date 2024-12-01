import socketio
from .connection_manager import ConnectionManager
from .namespaces.assistant_realtime import AssistantRealtimeNamespace
from .namespaces.default import DefaultNamespace

class SocketIORouter:
    def __init__(self, sio: socketio.AsyncServer, connection_manager: ConnectionManager):
        self.sio = sio
        self.connection_manager = connection_manager
        self.namespaces = []
        self.register_namespaces()

    def register_namespaces(self):
        """Register all namespace handlers"""
        self.namespaces.extend([
            DefaultNamespace(self.sio, self.connection_manager),
            AssistantRealtimeNamespace(self.sio, self.connection_manager)
        ])
