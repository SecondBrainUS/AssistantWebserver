from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pathlib import Path
import json
import logging
import tidalapi
import tidalapi.exceptions
from typing import Optional
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

router = APIRouter()

# Store pending auth sessions in memory (consider Redis for production)
_pending_auth_sessions = {}

class TidalAuthInitResponse(BaseModel):
    """Response model for initiating Tidal authentication"""
    auth_id: str
    verification_uri: str
    verification_uri_complete: str
    user_code: str
    device_code: str
    expires_in: int

class TidalAuthStatusResponse(BaseModel):
    """Response model for checking Tidal authentication status"""
    status: str  # "pending", "completed", "expired", "error"
    message: Optional[str] = None

class TidalSessionInfo(BaseModel):
    """Response model for current Tidal session info"""
    authenticated: bool
    expiry_time: Optional[str] = None
    user_id: Optional[int] = None
    message: Optional[str] = None

@router.post("/init", response_model=TidalAuthInitResponse)
async def init_tidal_auth(background_tasks: BackgroundTasks):
    """
    Initialize Tidal OAuth authentication flow.
    Returns the verification URL and codes for the user to authenticate.
    """
    try:
        session = tidalapi.Session()
        login, future = session.login_oauth()
        
        # Generate a unique auth ID for this session
        import uuid
        auth_id = str(uuid.uuid4())
        
        # Store the session and future for status checking
        _pending_auth_sessions[auth_id] = {
            "session": session,
            "future": future,
            "login": login,
            "status": "pending"
        }
        
        # Clean up old sessions after some time
        background_tasks.add_task(_cleanup_auth_session, auth_id, timeout=600)  # 10 minutes
        
        logger.info(f"Tidal auth initialized with ID: {auth_id}")
        
        return TidalAuthInitResponse(
            auth_id=auth_id,
            verification_uri=login.verification_uri,
            verification_uri_complete=login.verification_uri_complete,
            user_code=login.user_code,
            device_code=login.device_code,
            expires_in=login.expires_in
        )
        
    except HTTPError as e:
        logger.error(f"HTTP error during Tidal OAuth init: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to initialize Tidal authentication: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during Tidal OAuth init: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize Tidal authentication: {str(e)}"
        )

@router.get("/status/{auth_id}", response_model=TidalAuthStatusResponse)
async def check_tidal_auth_status(auth_id: str):
    """
    Check the status of a pending Tidal authentication.
    Poll this endpoint to see when the user has completed authentication.
    """
    if auth_id not in _pending_auth_sessions:
        raise HTTPException(
            status_code=404,
            detail="Authentication session not found or expired"
        )
    
    auth_data = _pending_auth_sessions[auth_id]
    
    # Check if the future is done
    if auth_data["future"].done():
        try:
            # This will raise an exception if auth failed
            auth_data["future"].result()
            
            # Save the session
            session = auth_data["session"]
            session_path = Path("secrets/tidal_session.json")
            _save_tidal_session(session, session_path)
            
            # Update status
            auth_data["status"] = "completed"
            
            logger.info(f"Tidal auth completed for ID: {auth_id}")
            
            return TidalAuthStatusResponse(
                status="completed",
                message="Tidal authentication successful! Session saved."
            )
        except Exception as e:
            auth_data["status"] = "error"
            logger.error(f"Tidal auth failed for ID {auth_id}: {e}")
            return TidalAuthStatusResponse(
                status="error",
                message=f"Authentication failed: {str(e)}"
            )
    
    return TidalAuthStatusResponse(
        status="pending",
        message="Waiting for user to complete authentication"
    )

@router.post("/complete/{auth_id}")
async def complete_tidal_auth(auth_id: str):
    """
    Manually trigger completion check and save for a pending authentication.
    This is an alternative to polling /status endpoint.
    """
    if auth_id not in _pending_auth_sessions:
        raise HTTPException(
            status_code=404,
            detail="Authentication session not found or expired"
        )
    
    auth_data = _pending_auth_sessions[auth_id]
    
    try:
        # Wait for the authentication to complete (with timeout)
        auth_data["future"].result(timeout=1)  # 1 second timeout
        
        # Save the session
        session = auth_data["session"]
        session_path = Path("secrets/tidal_session.json")
        _save_tidal_session(session, session_path)
        
        # Clean up
        _pending_auth_sessions.pop(auth_id, None)
        
        logger.info(f"Tidal auth completed and saved for ID: {auth_id}")
        
        return {
            "status": "completed",
            "message": "Tidal authentication successful and session saved!"
        }
        
    except TimeoutError:
        return {
            "status": "pending",
            "message": "Authentication not yet completed by user"
        }
    except Exception as e:
        logger.error(f"Error completing Tidal auth for ID {auth_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to complete authentication: {str(e)}"
        )

@router.get("/session/info", response_model=TidalSessionInfo)
async def get_tidal_session_info():
    """
    Get information about the current Tidal session.
    Returns whether a valid session exists and when it expires.
    """
    session_path = Path("secrets/tidal_session.json")
    
    if not session_path.exists():
        return TidalSessionInfo(
            authenticated=False,
            message="No Tidal session file found"
        )
    
    try:
        with open(session_path) as f:
            creds = json.load(f)
        
        import datetime as dt
        expiry_time = dt.datetime.fromisoformat(creds["expiry_time"])
        now = dt.datetime.now(expiry_time.tzinfo) if expiry_time.tzinfo else dt.datetime.now()
        
        if expiry_time > now:
            # Try to load the session to verify it's valid
            session = tidalapi.Session()
            ok = session.load_oauth_session(
                creds["token_type"],
                creds["access_token"],
                creds.get("refresh_token"),
                expiry_time,
            )
            
            if ok:
                user_id = session.user.id if hasattr(session, 'user') and session.user else None
                return TidalSessionInfo(
                    authenticated=True,
                    expiry_time=creds["expiry_time"],
                    user_id=user_id,
                    message="Valid Tidal session"
                )
        
        return TidalSessionInfo(
            authenticated=False,
            expiry_time=creds.get("expiry_time"),
            message="Session expired or invalid"
        )
        
    except Exception as e:
        logger.error(f"Error checking Tidal session info: {e}")
        return TidalSessionInfo(
            authenticated=False,
            message=f"Error reading session: {str(e)}"
        )

@router.post("/session/refresh")
async def refresh_tidal_session():
    """
    Attempt to refresh the current Tidal session using the refresh token.
    """
    session_path = Path("secrets/tidal_session.json")
    
    if not session_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No Tidal session file found. Please authenticate first."
        )
    
    try:
        with open(session_path) as f:
            creds = json.load(f)
        
        import datetime as dt
        session = tidalapi.Session()
        
        # Try to load and refresh
        ok = session.load_oauth_session(
            creds["token_type"],
            creds["access_token"],
            creds.get("refresh_token"),
            dt.datetime.fromisoformat(creds["expiry_time"]),
        )
        
        if ok:
            # Save the refreshed session
            _save_tidal_session(session, session_path)
            logger.info("Tidal session refreshed successfully")
            
            return {
                "status": "success",
                "message": "Tidal session refreshed successfully",
                "expiry_time": session.expiry_time.isoformat()
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Failed to refresh session. Please re-authenticate."
            )
            
    except Exception as e:
        logger.error(f"Error refreshing Tidal session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh session: {str(e)}"
        )

@router.delete("/session")
async def delete_tidal_session():
    """
    Delete the current Tidal session (logout).
    """
    session_path = Path("secrets/tidal_session.json")
    
    if not session_path.exists():
        return {
            "status": "success",
            "message": "No session to delete"
        }
    
    try:
        # Backup the old session
        import shutil
        backup_path = Path("secrets/old_tidal_session.json")
        shutil.copy(session_path, backup_path)
        
        # Delete current session
        session_path.unlink()
        
        logger.info("Tidal session deleted")
        
        return {
            "status": "success",
            "message": "Tidal session deleted. Backup saved to old_tidal_session.json"
        }
        
    except Exception as e:
        logger.error(f"Error deleting Tidal session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}"
        )

# Helper functions

def _save_tidal_session(session: tidalapi.Session, session_path: Path):
    """Save the OAuth session to a JSON file."""
    creds = {
        "token_type": session.token_type,
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expiry_time": session.expiry_time.isoformat(),
    }
    session_path.parent.mkdir(parents=True, exist_ok=True)
    with open(session_path, "w") as f:
        json.dump(creds, f, indent=2)
    logger.debug(f"Tidal session saved to {session_path}")

async def _cleanup_auth_session(auth_id: str, timeout: int):
    """Clean up auth session after timeout"""
    import asyncio
    await asyncio.sleep(timeout)
    if auth_id in _pending_auth_sessions:
        logger.info(f"Cleaning up expired Tidal auth session: {auth_id}")
        _pending_auth_sessions.pop(auth_id, None)
