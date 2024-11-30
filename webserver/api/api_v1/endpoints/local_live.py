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
import uuid
from fastapi.middleware.cors import CORSMiddleware

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
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        user_id = await get_current_user(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Generate a unique session ID for this connection
    session_id = str(uuid.uuid4())
    await manager.connect(websocket, user_id, session_id)

    # Optionally, send the session ID back to the client
    await websocket.send_json({"session_id": session_id})

    try:
        while True:
            data = await websocket.receive_text()
            # Process the received message and prepare a response
            response = f"Echo from server (Session {session_id}): {data}"
            await manager.send_personal_message(response, session_id)
    except WebSocketDisconnect:
        manager.disconnect(user_id, session_id)
    except Exception as e:
        manager.disconnect(user_id, session_id)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)