import socketio
import logging
from .connection_manager import ConnectionManager
from .router import SocketIORouter
from webserver.config import settings

logger = logging.getLogger(__name__)

def create_socketio_app():
    # Initialize the Socket.IO server
    sio = socketio.AsyncServer(
        async_mode='asgi',
        logger=True,
        engineio_logger=True,
        cors_allowed_origins=settings.CORS_ALLOWED_ORIGINS,
        ping_timeout=60,
        ping_interval=25,
        transports=['websocket', 'polling'],
        always_connect=True,
    )

    # Create the ASGI application
    sio_app = socketio.ASGIApp(sio)

    # Initialize the connection manager
    connection_manager = ConnectionManager()

    # Register all namespaces via the router
    SocketIORouter(sio, connection_manager)

    return sio_app

# Create the application instance
sio_app = create_socketio_app()
