from fastapi import APIRouter
from .endpoints.run import router as router_module
from .endpoints.auth import router as router_auth
from .endpoints.chat import router as router_chat
from .endpoints.model import router as router_model
from .endpoints.aisuitellm import router as router_aisuitellm
from .endpoints.prompt_compiler import router as router_prompt_compiler
from .endpoints.openai_api import router as router_openai_api
from .middleware.authentication import VerifyAccessTokenMiddleware, GetSessionIdMiddleware

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(router_auth, prefix="/auth", tags=["Auth"])
api_router.include_router(router_module, prefix="/run", tags=["Run"])
api_router.include_router(router_chat, prefix="/chat", tags=["Chat"])
api_router.include_router(router_model, prefix="/model", tags=["Model"])
api_router.include_router(router_aisuitellm, prefix="/aisuite", tags=["AISuiteLLM"])
api_router.include_router(router_prompt_compiler, prefix="/prompt_compiler", tags=["Prompt Compiler"])
api_router.include_router(router_openai_api, prefix="/openai", tags=["OpenAI", "Raw"])
