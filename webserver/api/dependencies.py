from fastapi import Request, HTTPException, Depends, BackgroundTasks
from jose import jwt
import json
from datetime import datetime
import aiomcache
from sqlalchemy.orm import Session
from webserver.config import settings
from webserver.db.memcache.connection import get_memcache_client
from webserver.db.assistantdb.connection import get_db
from webserver.db.assistantdb.auth_models import UserSession, User
import logging

logger = logging.getLogger(__name__)

async def verify_access_token(request: Request):
    """Verify the access token from cookies"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="No access token found in cookies"
        )

    try:
        payload = jwt.decode(
            access_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("token_type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        request.state.jwt_payload = payload
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def cache_session(
    memcache_client: aiomcache.Client,
    session_id: str,
    session_data: dict
):
    """Background task to cache session data"""
    # Cache data with string dates
    session_cache_data = {
        **session_data,
        "session_id": str(session_data["session_id"]),
        "user_id": str(session_data["user_id"]),
        "session_expires": session_data["session_expires"].isoformat(),
        "access_token_expires": session_data["access_token_expires"].isoformat(),
        "refresh_token_expires": session_data["refresh_token_expires"].isoformat(),
        "created": session_data["created"].isoformat(),
        "updated": session_data["updated"].isoformat(),
    }
    try:
        await memcache_client.set(
            f"session:{session_id}".encode(),
            json.dumps(session_cache_data).encode(),
            exptime=3600
        )
    except Exception as e:
        logger.error(f"Failed to update cache for session {session_id}: {str(e)}")

async def cache_user(
    memcache_client: aiomcache.Client,
    user_id: str,
    user_data: dict
):
    """Background task to cache user data"""
    user_cache_data = {
        **user_data,
        "user_id": str(user_data["user_id"]),
        "created": user_data["created"].isoformat() if user_data.get("created") else None,
        "updated": user_data["updated"].isoformat() if user_data.get("updated") else None,
        "last_login": user_data["last_login"].isoformat() if user_data.get("last_login") else None,
    }
    try:
        await memcache_client.set(
            f"user:{user_id}".encode(),
            json.dumps(user_cache_data).encode(),
            exptime=3600
        )
    except Exception as e:
        logger.error(f"Failed to update cache for user {user_id}: {str(e)}")

async def get_session(
    request: Request,
    background_tasks: BackgroundTasks,
    memcache_client: aiomcache.Client = Depends(get_memcache_client),
    db: Session = Depends(get_db)
):
    """Get and verify session data from cookies"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, content={"detail": "No session ID"})
    
    # Check cache for session
    session_data = None
    cached_session = await memcache_client.get(f"session:{session_id}".encode())
    if cached_session:
        session_dict = json.loads(cached_session.decode())
        session_data = {
            **session_dict,
            "session_expires": datetime.fromisoformat(session_dict["session_expires"]),
            "access_token_expires": datetime.fromisoformat(session_dict["access_token_expires"]),
            "refresh_token_expires": datetime.fromisoformat(session_dict["refresh_token_expires"]),
            "created": datetime.fromisoformat(session_dict["created"]),
            "updated": datetime.fromisoformat(session_dict["updated"]),
        }
    # If not in cache, check DB
    else:
        db_session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
        # If not in DB, raise error
        if not db_session:
            raise HTTPException(status_code=401, detail="Invalid session")
        # Reformat session data
        session_dict = db_session.to_dict()
        session_data = {
            **session_dict,
            "session_id": str(session_dict["session_id"]),
            "user_id": str(session_dict["user_id"]),
        }
        # Add background task to cache session data
        background_tasks.add_task(
            cache_session,
            memcache_client,
            session_id,
            session_data
        )

    # Check cache for user
    user_data = None
    cached_user = await memcache_client.get(f"user:{session_data['user_id']}".encode())
    if cached_user:
        user_dict = json.loads(cached_user.decode())
        user_data = {
            **user_dict,
        }
    else:
        db_user = db.query(User).filter(User.user_id == session_data['user_id']).first()
        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid user")
        user_dict = db_user.to_dict()
        user_data = {
            **user_dict,
            "user_id": str(user_dict["user_id"]),
        }
        # Add background task to cache user data
        background_tasks.add_task(
            cache_user,
            memcache_client,
            user_data['user_id'],
            user_data
        )

    # Reformat user data
    user_state = {
        "user_id": user_data.get("user_id"),
        "auth_type": user_data.get("auth_type"),
        "email": user_data.get("email"),
        "picture": user_data.get("picture"),
        "name": user_data.get("name")
    }

    # Reformat session data
    session_state = {
        "session_id": session_data.get("session_id"),
        "user_id": session_data.get("user_id"),
        "access_token": session_data.get("access_token"),
        "refresh_token": session_data.get("refresh_token"),
        "session_expires": session_data.get("session_expires"),
        "access_token_expires": session_data.get("access_token_expires"),
        "refresh_token_expires": session_data.get("refresh_token_expires"),
        "created": session_data.get("created"),
        "updated": session_data.get("updated"),
    }

    # Set state
    request.state.user = user_state
    request.state.session = session_state