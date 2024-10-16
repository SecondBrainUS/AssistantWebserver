from fastapi import APIRouter
from .endpoints.run import router as router_module

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(router_module, prefix="/run", tags=["Run"])
