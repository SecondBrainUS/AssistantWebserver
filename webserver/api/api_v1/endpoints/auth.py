import logging
from fastapi import APIRouter, Depends, Request, HTTPException, Response, Cookie
from authlib.integrations.starlette_client import OAuth
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from webserver.config import settings
from webserver.db.assistantdb.connection import get_db
from webserver.db.assistantdb.model import User, AuthGoogle
from jose import jwt
import uuid
from datetime import datetime, timedelta
from webserver.api.dependencies import get_current_user
import time

logger = logging.getLogger(__name__)

router = APIRouter()

oauth = OAuth()
google = oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived access token
REFRESH_TOKEN_EXPIRE_DAYS = 7    # Longer-lived refresh token

async def create_or_update_user(db: Session, provider: str, claims: dict, token: dict):
    email = claims.get("email")
    provider_user_id = claims.get("sub")  # For Google/Microsoft, "sub" is the unique user ID

    if not email or not provider_user_id:
        raise HTTPException(status_code=400, detail="Invalid user info from provider")

    user = db.query(User).filter(User.email == email).one_or_none()
    if not user:
        # Create new user
        user = User(email=email, auth_type=provider)
        db.add(user)
        db.commit()
        db.refresh(user)

    if provider == "google":
        # Upsert Google details
        details = db.query(AuthGoogle).filter(AuthGoogle.user_id == user.user_id).one_or_none()
        if not details:
            details = AuthGoogle(
                user_id=user.user_id,
                google_user_id=provider_user_id,
                access_token=token.get("access_token"),
                refresh_token=token.get("refresh_token"),
                token_expiry=str(token.get("expires_at"))
            )
            db.add(details)
        else:
            details.google_user_id = provider_user_id
            details.access_token = token.get("access_token")
            details.refresh_token = token.get("refresh_token")
            details.token_expiry = str(token.get("expires_at"))

    db.commit()
    return user

def create_jwt_token(user, userinfo):
    payload = {
        "sub": str(user.user_id),
        "user_id": str(user.user_id),
        "email": user.email,
        "auth_type": user.auth_type,
        "picture": userinfo.get("picture"),
        "name": userinfo.get("name")
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token

def create_tokens(user_data: dict):
    """Create access and refresh tokens"""
    # Access token payload
    access_token_expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_payload = {
        **user_data,
        "exp": access_token_expires,
        "token_type": "access"
    }
    
    # Refresh token payload
    refresh_token_expires = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_payload = {
        "sub": str(user_data["sub"]),
        "exp": refresh_token_expires,
        "token_type": "refresh"
    }
    
    access_token = jwt.encode(access_token_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_token_payload, settings.JWT_REFRESH_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return access_token, refresh_token

@router.get("/{provider}/login")
async def login(provider: str, request: Request):
    if provider not in ["google"]:
        raise HTTPException(status_code=404, detail="Provider not supported")
    logger.info("Starting Google OAuth flow")
    redirect_uri = f"{settings.BASE_URL}/api/v1/auth/{provider}/callback"
    logger.info(f"Redirect URI set to: {redirect_uri}")
    if provider == "google":
        try:
            auth_redirect = await google.authorize_redirect(request, redirect_uri)
            logger.info("Successfully created Google auth redirect")
            return auth_redirect
        except Exception as e:
            logger.error(f"Error in Google auth redirect: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="OAuth initialization failed")
    else:
        return {"message": "Provider not supported"}

@router.get("/{provider}/callback")
async def callback(provider: str, request: Request, response: Response, db: Session = Depends(get_db)):
    if provider not in ["google"]:
        raise HTTPException(status_code=404, detail="Provider not supported")

    try:
        logger.info("Starting OAuth callback processing")
        if provider == "google":
            # Log the incoming request details
            logger.debug(f"Callback request query params: {request.query_params}")
            logger.debug(f"Callback request headers: {request.headers}")
            
            token = await google.authorize_access_token(request)
            logger.info("Successfully obtained OAuth token")
            
            userinfo = token.get('userinfo')
            if not userinfo:
                logger.info("Userinfo not in token, fetching explicitly")
                userinfo = await google.parse_id_token(request, token)
            
            logger.info(f"Obtained user info for email: {userinfo.get('email')}")
        else:
            return {"message": "Provider not supported"}

        user = await create_or_update_user(db, provider, userinfo, token)
        logger.info(f"User created/updated in database: {user.email}")
        
        # Create tokens with user data
        user_data = {
            "sub": str(user.user_id),
            "email": user.email,
            "auth_type": user.auth_type,
            "picture": userinfo.get("picture"),
            "name": userinfo.get("name")
        }
        access_token, refresh_token = create_tokens(user_data)
        logger.info("JWT tokens created successfully")

        # Set cookies with simpler settings since we're on same origin
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            samesite="lax",  # Can use lax now
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/"  # No need for domain
        )
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            samesite="lax",  # Can use lax now
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/"  # No need for domain
        )

        # Redirect to frontend URL (not the API URL)
        frontend_url = "http://localhost:3000"  # Vite's default port
        if settings.SYSTEM_MODE == "prod":
            frontend_url = settings.FRONTEND_URL
            
        redirect_url = f"{frontend_url}?auth=success&ts={int(time.time())}"
        logger.info(f"Redirecting to: {redirect_url}")
        
        return RedirectResponse(
            url=redirect_url,
            status_code=302
        )
        
    except Exception as e:
        logger.error("Auth callback error", exc_info=True)
        logger.exception(e)
        # Return more detailed error in development
        if settings.SYSTEM_MODE == "dev":
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=400, detail="Authentication failed")

@router.post("/refresh")
async def refresh_token(response: Response, refresh_token: str = Cookie(None)):
    """Endpoint to refresh access token using refresh token"""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    try:
        payload = jwt.decode(
            refresh_token, 
            settings.JWT_REFRESH_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify it's a refresh token
        if payload.get("token_type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        # Create new access token
        user_data = {
            "sub": payload["sub"],
            "token_type": "access"
        }
        new_access_token, _ = create_tokens(user_data)
        
        # Set new access token cookie
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        return {"message": "Token refreshed"}
        
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.get("/status")
async def auth_status(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Return current user information"""
    logger.info("Auth status check received")
    logger.debug(f"Request cookies: {request.cookies}")
    logger.debug(f"Request headers: {request.headers}")
    return current_user

@router.post("/logout")
async def logout(response: Response):
    """Clear auth cookies"""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}
