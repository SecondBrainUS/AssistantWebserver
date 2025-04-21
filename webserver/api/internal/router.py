from fastapi import APIRouter
from .endpoints.health import router as router_health

internal_router = APIRouter(prefix="/internal")
internal_router.include_router(router_health, tags=["Health"]) 