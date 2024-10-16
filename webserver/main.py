from fastapi import FastAPI
from webserver.api.api_v1.router import api_router
from webserver.middleware.server_exceptions import load_exception_handlers
app = FastAPI()

load_exception_handlers(app)
app.include_router(api_router)
