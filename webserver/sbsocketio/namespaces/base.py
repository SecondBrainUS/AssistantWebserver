from abc import ABC, abstractmethod
import socketio
from ..connection_manager import ConnectionManager

class BaseNamespace(ABC):
    def __init__(self, sio: socketio.AsyncServer, connection_manager: ConnectionManager):
        self.sio = sio
        self.connection_manager = connection_manager
        self.namespace = self.get_namespace()
        self.register_handlers()

    @abstractmethod
    def get_namespace(self) -> str:
        """Return the namespace string for this handler group"""
        pass

    @abstractmethod
    def register_handlers(self):
        """Register all event handlers for this namespace"""
        pass
