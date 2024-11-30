from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from jose import jwt, JWTError
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status, Depends
from webserver.util.websocket_session_manager import ConnectionManager
from webserver.logger_config import init_logger
import logging

init_logger()

logger = logging.getLogger(__name__)

# Secret key for JWT encoding/decoding
SECRET_KEY = "your-secret-key"  # Replace with your actual secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/local/live/token")
manager = ConnectionManager()


# User model for authentication
class User(BaseModel):
    username: str
    password: str

# Function to create JWT access tokens
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    logger.debug("[WS LOCAL LIVE] Creating access token for data: %s", data)
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug("[WS LOCAL LIVE] Access token created: %s", token)
    return token

# Endpoint to authenticate users and provide JWT tokens
@router.post("/token")
async def login(user: User):
    logger.info("[WS LOCAL LIVE] Login attempt for user: %s", user.username)
    # Implement actual authentication logic here
    # For demonstration, accept any username/password
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info("[WS LOCAL LIVE] Access token generated for user: %s", user.username)
    return {"access_token": access_token, "token_type": "bearer"}

# Dependency to get the current user from the token
async def get_current_user(token: str = Depends(oauth2_scheme)):
    logger.debug("[WS LOCAL LIVE] Decoding token: %s", token)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            logger.warning("[WS LOCAL LIVE] Token does not contain a username")
            raise credentials_exception
        logger.info("[WS LOCAL LIVE] Token decoded successfully for user: %s", username)
    except JWTError:
        logger.error("[WS LOCAL LIVE] JWTError occurred while decoding token")
        raise credentials_exception
    return username

@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("[WS LOCAL LIVE] WebSocket connection attempt")
    # Initialize session for user
    session_id = await manager.connect(websocket)
    logger.info("[WS LOCAL LIVE] Session initialized: %s", session_id)
    try:
        await manager.send_personal_message(f"Session initialized: {session_id}", session_id)
        while True:
            # Receive message from the user
            data = await websocket.receive_text()
            logger.debug("[WS LOCAL LIVE] Received message from session %s: %s", session_id, data)

            # Send a response back to the user
            response = f"Echo from session {session_id}: {data}"
            await manager.send_personal_message(response, session_id)
            logger.debug("[WS LOCAL LIVE] Sent response to session %s: %s", session_id, response)
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info("Session %s disconnected", session_id)