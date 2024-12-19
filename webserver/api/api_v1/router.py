from fastapi import APIRouter
from .endpoints.run import router as router_module
from .endpoints.local_live import router as router_local_live
from .endpoints.auth import router as router_auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(router_auth, prefix="/auth", tags=["Auth"])
api_router.include_router(router_module, prefix="/run", tags=["Run"])
api_router.include_router(router_local_live, prefix="/local/live", tags=["Local Live"])
