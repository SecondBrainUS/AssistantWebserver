from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from webserver.api.api_v1.router import api_router
from webserver.middleware.server_exceptions import load_exception_handlers
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_exception_handlers(app)
app.include_router(api_router)
