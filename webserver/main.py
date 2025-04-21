from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from webserver.api.api_v1.router import api_router
from webserver.api.internal.router import internal_router
from webserver.middleware.server_exceptions import load_exception_handlers
from webserver.sbsocketio import sio_app
from starlette.middleware.sessions import SessionMiddleware
from webserver.config import settings
from webserver.db.chatdb.db import mongodb_client
from webserver.util.file_conversions import shutdown_thread_pool
import logging
import uvicorn

logging.getLogger('socketio.server').setLevel(logging.WARNING)
logging.getLogger('engineio.server').setLevel(logging.WARNING)
logging.getLogger('pymongo').setLevel(logging.WARNING)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

Instrumentator().instrument(app).expose(app, include_in_schema=False)

app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET_KEY)
load_exception_handlers(app)
app.include_router(api_router)
app.include_router(internal_router)
app.mount("/", sio_app)

@app.on_event("startup")
async def startup_event():
    await mongodb_client.connect()

@app.on_event("shutdown")
async def shutdown_event():
    # Shutdown the file conversion thread pool
    shutdown_thread_pool()
    # Close MongoDB connection
    await mongodb_client.close()

def start():
    uvicorn.run("webserver.main:app", host="0.0.0.0", port=settings.PORT, reload=True)