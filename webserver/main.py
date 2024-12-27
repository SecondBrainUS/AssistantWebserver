from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from webserver.api.api_v1.router import api_router
from webserver.middleware.server_exceptions import load_exception_handlers
from webserver.sbsocketio import sio_app
from starlette.middleware.sessions import SessionMiddleware
from webserver.config import settings
from webserver.db.chatdb.db import mongodb_client
import uvicorn

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY, max_age=3600)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],
    # allow_origins=[settings.FRONTEND_URL],
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

load_exception_handlers(app)
app.include_router(api_router)
app.mount("/", sio_app)

@app.on_event("startup")
async def startup_event():
    await mongodb_client.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await mongodb_client.close()

def start():
    """Launched with `poetry run dev` at the root level"""
    uvicorn.run("webserver.main:app", host="0.0.0.0", port=8000, reload=True)
