# Socket.IO Implementation

This directory contains the Socket.IO implementation for the AssistantWebserver, providing real-time communication between clients and AI assistants.

## Overview

The Socket.IO implementation is organized around:

1. **Namespaces**: Different Socket.IO namespaces for different types of connections
2. **Rooms**: Socket.IO rooms for grouping connections
3. **AssistantRoom**: Custom room implementation that adds AI capabilities
4. **Connection Management**: Tracking user connections and sessions

## Directory Structure

```
sbsocketio/
├── __init__.py                       # Package initialization
├── socketio_app.py                   # Socket.IO application setup
├── router.py                         # Socket.IO router
├── connection_manager.py             # User connection management
├── assistant_room.py                 # Base AssistantRoom class
├── assistant_room_manager.py         # Manages AssistantRoom instances
├── assistant_room_aisuite.py         # AISuite implementation
├── assistant_room_openai_realtime.py # OpenAI implementation
└── namespaces/                       # Socket.IO namespace handlers
    ├── __init__.py
    ├── default.py                    # Default namespace
    └── assistant_realtime.py         # Assistant realtime namespace
└── models/                           # Socket.IO data models
```

## Core Components

### SocketIO App (`socketio_app.py`)

Sets up the Socket.IO server and mounts it to the FastAPI application:

```python
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ALLOWED_ORIGINS
)

sio_app = socketio.ASGIApp(
    sio,
    socketio_path='socket.io'
)

# Socket.IO router initialization
connection_manager = ConnectionManager()
router = SocketIORouter(sio, connection_manager)
```

### Connection Manager (`connection_manager.py`)

Manages user connections and keeps track of user-to-socket mappings:

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, str] = {}  # sid -> user_id
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set(sid)

    def add_connection(self, sid: str, user_id: str):
        """Add a connection for a user"""
        self.active_connections[sid] = user_id
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(sid)

    def remove_connection(self, sid: str) -> Optional[str]:
        """Remove a connection and return the associated user_id if found"""
        user_id = self.active_connections.pop(sid, None)
        if user_id:
            self.user_connections.get(user_id, set()).discard(sid)
            if not self.user_connections.get(user_id):
                self.user_connections.pop(user_id, None)
        return user_id

    def get_user_id(self, sid: str) -> Optional[str]:
        """Get user_id for a connection"""
        return self.active_connections.get(sid)

    def get_user_connections(self, user_id: str) -> Set[str]:
        """Get all connections for a user"""
        return self.user_connections.get(user_id, set())
```

### Assistant Room Manager (`assistant_room_manager.py`)

Manages the creation and lifecycle of AssistantRoom instances:

```python
class AssistantRoomManager:
    def __init__(self, connection_manager: ConnectionManager, sio: socketio.AsyncServer):
        self.sio: socketio.AsyncServer = sio
        self.rooms: Dict[str, AssistantRoom] = {}
        self.chatid_roomid_map: Dict[str, str] = {}
        self.connection_manager: ConnectionManager = connection_manager

    async def create_room(self, room_id: str, namespace: str, model_api_source: str, model_id: str, chat_id: str) -> bool:
        """Create a new room with appropriate API instance"""
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
            return True
        else:
            logger.error(f"Failed to create room {room_id}")
            return False
```

## AssistantRoom Classes

### Base AssistantRoom (`assistant_room.py`)

Abstract base class that provides common functionality for all assistant room implementations:

```python
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
            
        # Tool setup - loads all available tools
        self.assistant_functions = AssistantFunctions(...)
        self.tool_map = {...}
        self.tool_usage_guide = self._generate_tool_usage_guide()
        
    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def cleanup(self):
        pass
        
    # User management methods
    def add_user(self, sid: str):
        """Add a user to the room"""
        self.connected_users.add(sid)
        
    def remove_user(self, sid: str):
        """Remove a user from the room"""
        self.connected_users.discard(sid)
        
    # Communication methods
    async def broadcast(self, event_type: str, sid: str, data: dict) -> None:
        """Broadcast a message to all users in the room"""
        await self.sio.emit(
            event_type,
            data,
            room=self.room_id,
            skip_sid=sid,
            namespace=self.namespace
        )
        
    # Storage methods
    async def save_message(self, message: dict):
        """Save a message to the database"""
        messages_collection = mongodb_client.db["messages"]
        await messages_collection.insert_one(message)
```

### AI Suite Room (`assistant_room_aisuite.py`)

Implementation for the AI Suite integration:

```python
class AiSuiteRoom(AssistantRoom):
    """AssistantRoom implementation for AISuite API"""
    
    async def initialize(self) -> bool:
        """Initialize the AISuite room"""
        try:
            self.aisuite_client = aisuite.Client(api_key=settings.AISUITE_API_KEY)
            # Additional initialization...
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AISuite room: {e}")
            return False
            
    async def handle_message(self, message: dict, sid: str) -> None:
        """Handle incoming messages in the AISuite room"""
        # Process the message...
        
    async def cleanup(self):
        """Clean up resources when the room is closed"""
        # Cleanup code...
```

### OpenAI Realtime Room (`assistant_room_openai_realtime.py`)

Implementation for the OpenAI streaming API:

```python
class OpenAiRealTimeRoom(AssistantRoom):
    """AssistantRoom implementation for OpenAI streaming API"""
    
    async def initialize(self) -> bool:
        """Initialize the OpenAI Realtime room"""
        try:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            # Additional initialization...
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI room: {e}")
            return False
            
    async def handle_message(self, message: dict, sid: str) -> None:
        """Handle incoming messages in the OpenAI room"""
        # Process message and stream response...
        
    async def cleanup(self):
        """Clean up resources when the room is closed"""
        # Cleanup code...
```

## Namespace Handlers

### Assistant Realtime Namespace (`namespaces/assistant_realtime.py`)

Handles the `/assistant/realtime` namespace:

```python
class AssistantRealtimeNamespace(BaseNamespace):
    def __init__(self, sio, connection_manager):
        super().__init__(sio, connection_manager)
        self.namespace = "/assistant/realtime"
        self.room_manager = AssistantRoomManager(connection_manager, sio)
        self.register_handlers()

    def register_handlers(self):
        """Register Socket.IO event handlers for this namespace"""
        
        @self.sio.on('connect', namespace=self.namespace)
        async def connect(sid, environ, auth):
            # Authenticate connection...
            
        @self.sio.on('disconnect', namespace=self.namespace)
        async def disconnect(sid):
            # Handle disconnection...
            
        @self.sio.on('create_room', namespace=self.namespace)
        async def create_assistant_room(sid, data):
            # Create AssistantRoom...
            
        @self.sio.on('join_room', namespace=self.namespace)
        async def join_assistant_room(sid, data):
            # Join AssistantRoom...
            
        @self.sio.on('leave_room', namespace=self.namespace)
        async def leave_assistant_room(sid, data):
            # Leave AssistantRoom...
```

## Socket.IO Router (`router.py`)

Routes Socket.IO connections to the appropriate namespace handlers:

```python
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
```

## Creating a New AssistantRoom Implementation

To implement a new AssistantRoom for a different AI provider:

1. Create a new file (e.g., `assistant_room_custom.py`)
2. Extend the AssistantRoom class
3. Implement the required methods
4. Register the new room type in AssistantRoomManager

Example:

```python
class CustomAssistantRoom(AssistantRoom):
    """Custom AssistantRoom implementation"""
    
    async def initialize(self) -> bool:
        """Initialize the custom room"""
        try:
            # Initialize your custom AI client
            self.custom_client = CustomAIClient(api_key=settings.CUSTOM_AI_KEY)
            # Additional initialization...
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Custom room: {e}")
            return False
            
    async def handle_message(self, message: dict, sid: str) -> None:
        """Handle incoming messages in the custom room"""
        # Process the message...
        # Send responses...
        
    async def cleanup(self):
        """Clean up resources when the room is closed"""
        # Cleanup code...
```

Then add your implementation to the AssistantRoomManager:

```python
room_types = {
    "openai_realtime": OpenAiRealTimeRoom,
    "aisuite": AiSuiteRoom,
    "custom": CustomAssistantRoom,  # Add your implementation
}
```

## Socket.IO Events

For a complete reference of Socket.IO events, see the [Socket.IO Events Documentation](../../docs/SOCKETIO_EVENTS.md). 