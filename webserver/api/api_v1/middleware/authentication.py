from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt
import json
import aiomcache
from webserver.config import settings
from webserver.db.memcache.connection import get_memcache_client
from webserver.db.assistantdb.connection import get_db
from webserver.db.assistantdb.model import UserSession, User
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class VerifyAccessTokenMiddleware(BaseHTTPMiddleware):
    """ Middleware to verify access token from cookies """
    def __init__(self, app: FastAPI):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        access_token = request.cookies.get("access_token")
        if not access_token:
            return JSONResponse(status_code=401, content={"detail": "No access token found in cookies"})
        jtw_payload = self.verify_access_token(access_token)
        request.state.jwt_payload = jtw_payload
        return await call_next(request)
    
    def verify_access_token(self, access_token: str):
        try:
            payload = jwt.decode(
                access_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            if payload.get("token_type") != "access":
                raise HTTPException(status_code=401, detail="Invalid token type")
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

class GetSessionIdMiddleware(BaseHTTPMiddleware):
    """ Middleware to get session ID from cookies """
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.memcache_client = None
        self.db = None
    
    async def dispatch(self, request: Request, call_next):
        # Lazy initialization of connections
        if not self.memcache_client:
            self.memcache_client = await get_memcache_client()
        if not self.db:
            self.db = next(get_db())

        session_id = request.cookies.get("session_id")
        if not session_id:
            return JSONResponse(status_code=401, content={"detail": "No session ID"})
        
        # Check cache first for session data
        cached_session = await self.check_cache(f"session:{session_id}")
        if cached_session:
            session_dict = json.loads(cached_session.decode())
            
            # Convert string dates back to datetime for request.state
            session_data = {
                **session_dict,
                "session_expires": datetime.fromisoformat(session_dict["session_expires"]),
                "access_token_expires": datetime.fromisoformat(session_dict["access_token_expires"]),
                "refresh_token_expires": datetime.fromisoformat(session_dict["refresh_token_expires"]),
                "created": datetime.fromisoformat(session_dict["created"]),
                "updated": datetime.fromisoformat(session_dict["updated"]),
            }
            
            # Get user data from cache using user_id
            cached_user = await self.check_cache(f"user:{session_dict['user_id']}")
            if cached_user:
                request.state.user = json.loads(cached_user.decode())
                request.state.session = session_data
                return await call_next(request)
            
        # If not in cache, check DB
        db_data = await self.get_session_from_db(session_id)
        if not db_data:
            return JSONResponse(status_code=401, content={"detail": "Invalid session"})
        
        user_data = {
            "user_id": db_data.user_id,
            "auth_type": db_data.auth_type,
            "email": db_data.email,
            "picture": db_data.picture,
            "name": db_data.name
        }

        session_state_data = {
            "session_id": db_data.session_id,
            "user_id": db_data.user_id,
            "access_token": db_data.access_token,
            "refresh_token": db_data.refresh_token,
            "session_expires": db_data.session_expires,
            "access_token_expires": db_data.access_token_expires,
            "refresh_token_expires": db_data.refresh_token_expires,
            "created": db_data.created,
            "updated": db_data.updated,
        }

        # Cache data converts dates to strings
        session_cache_data = {
            **session_state_data,
            "session_expires": db_data.session_expires.isoformat(),
            "access_token_expires": db_data.access_token_expires.isoformat(),
            "refresh_token_expires": db_data.refresh_token_expires.isoformat(),
            "created": db_data.created.isoformat(),
            "updated": db_data.updated.isoformat(),
        }

        # Set state
        request.state.user = user_data
        request.state.session = session_state_data

        # Create background task to update cache
        async def update_cache():
            try:
                # Cache session data
                await self.memcache_client.set(
                    f"session:{session_id}".encode(),
                    json.dumps(session_cache_data).encode(),
                    exptime=3600  # Cache for 1 hour
                )
                # Cache user data
                await self.memcache_client.set(
                    f"user:{db_data.user_id}".encode(),
                    json.dumps(user_data).encode(),
                    exptime=3600  # Cache for 1 hour
                )
            except Exception as e:
                logger.error(f"Failed to update cache for session {session_id}: {str(e)}")

        # Add background task
        request.state.background = BackgroundTasks()
        request.state.background.add_task(update_cache)

        return await call_next(request)

    async def check_cache(self, key: str) -> bytes:
        try:
            return await self.memcache_client.get(key.encode())
        except Exception:
            return None

    async def get_session_from_db(self, session_id: str):
        try:
            session = self.db.query(UserSession).filter(
                UserSession.session_id == session_id
            ).first()
            return session
        except Exception:
            return None
        
    async def get_user_from_db(self, user_id: str):
        try:
            user = self.db.query(User).filter(User.user_id == user_id).first()
            return user
        except Exception:
            return None

    def check_access_token(self, access_token: str):
        # TODO: check if access_token is in db
        pass

