from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, Response, HTTPException, Security
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from webserver.config import settings
from webserver.db.assistantdb.connection import get_db
from webserver.db.assistantdb.auth_models import User, AuthGoogle, UserSession, UserWhitelist
import uuid
import aiomcache
import logging
import json
from webserver.db.memcache.connection import get_memcache_client
from webserver.logger_config import init_logger
from prometheus_client import Counter
from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError

init_logger()

logger = logging.getLogger(__name__)

# Prometheus metrics
AUTH_SUCCESS = Counter('auth_success_total', 'Successful authentication attempts', ['provider'])
AUTH_FAILURE = Counter('auth_failure_total', 'Failed authentication attempts', ['provider', 'reason'])
WHITELIST_VIOLATION = Counter('auth_whitelist_violation_total', 'Authentication attempts from non-whitelisted users', ['email', 'provider'])
TOKEN_VALIDATION = Counter('token_validation_total', 'Token validation attempts', ['status', 'reason'])
TOKEN_REFRESH = Counter('token_refresh_total', 'Token refresh attempts', ['status', 'reason'])
AUTH_ERROR = Counter('auth_error_total', 'Authentication errors by type', ['endpoint', 'error_type'])

# TODO: long term, use guest sessionid instead of userid for temp tokens during auth login process

router = APIRouter()

oauth = OAuth()
google = oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

async def create_or_update_user(db: Session, provider: str, claims: dict, token: dict):
    """ Upserts the user into the database. Determines user by email."""
    email = claims.get("email")
    provider_user_id = claims.get("sub")  # For Google/Microsoft, "sub" is the unique user ID

    if not email or not provider_user_id:
        raise HTTPException(status_code=400, detail="Invalid user info from provider")

    user = db.query(User).filter(User.email == email).one_or_none()
    if not user:
        # Create new user (auto created UUID in DB and refresh into user object)
        user = User(email=email, auth_type=provider, picture=claims.get("picture"), name=claims.get("name"))
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

def create_temp_jwt_token(user_data: dict):
    """Creates a temporary JWT token for the login process"""
    payload = {
        "sub": user_data["sub"],
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "token_type": "temp",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_tokens(user_data: dict):
    """Create access and refresh tokens"""
    # Access token payload
    access_token_expires = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_payload = {
        **user_data,
        "exp": access_token_expires,
        "token_type": "access"
    }
    
    # Refresh token payload
    refresh_token_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_payload = {
        "sub": str(user_data["sub"]),
        "exp": refresh_token_expires,
        "token_type": "refresh"
    }
    
    access_token = jwt.encode(access_token_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_token_payload, settings.JWT_REFRESH_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return access_token, refresh_token

async def verify_access_token(request: Request):
    logger.info(f"[AUTH] Verifying access token for {request.client.host}")
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
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="JWT error")

async def get_current_user(request: Request):
    pass

@router.get("/{provider}/login")
async def login(provider: str, request: Request):
    """Redirect to the provider's login page"""
    if provider not in ["google"]:
        raise HTTPException(status_code=404, detail="Provider not supported")
    redirect_uri = f"{settings.BASE_URL}{settings.BASE_PATH}/api/v1/auth/{provider}/callback"
    if provider == "google":
        return await google.authorize_redirect(request, redirect_uri)
    else:
        return {"message": "Provider not supported"}

@router.get("/{provider}/callback")
async def callback(provider: str, request: Request, response: Response, db: Session = Depends(get_db)):
    """Callback from the provider's login page. Upserts the user. Creates a temporary token and redirects"""
    if provider not in ["google"]:
        AUTH_FAILURE.labels(provider=provider, reason="unsupported_provider").inc()
        logger.warning(f"[AUTH] Unsupported provider login attempt: {provider} from IP {request.client.host}")
        raise HTTPException(status_code=404, detail="Provider not supported")

    try:
        token = None
        userinfo = None
        if provider == "google":
            try:
                token = await google.authorize_access_token(request)
            except MismatchingStateError:
                AUTH_FAILURE.labels(provider=provider, reason="csrf_token_mismatch").inc()
                logger.warning(f"[AUTH] CSRF state token mismatch - IP: {request.client.host}")
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid authentication state. Please try logging in again."
                )
            except OAuthError as e:
                AUTH_FAILURE.labels(provider=provider, reason="oauth_error").inc()
                logger.error(f"[AUTH] OAuth error - Provider: {provider}, IP: {request.client.host}, Error: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail="Authentication error. Please try again."
                )
                
            userinfo = token.get('userinfo')
            
            if not userinfo:
                AUTH_FAILURE.labels(provider=provider, reason="no_userinfo").inc()
                logger.error(f"[AUTH] No userinfo in token for IP {request.client.host}")
                raise HTTPException(status_code=401, detail="No userinfo")
                
            if userinfo.get("email_verified") != True:
                AUTH_FAILURE.labels(provider=provider, reason="email_not_verified").inc()
                logger.warning(f"[AUTH] Unverified email login attempt: {userinfo.get('email')} from IP {request.client.host}")
                raise HTTPException(status_code=401, detail="Email not verified")
                
            email = userinfo.get("email")
            if not email:
                AUTH_FAILURE.labels(provider=provider, reason="no_email").inc()
                logger.error(f"[AUTH] No email in userinfo for IP {request.client.host}")
                raise HTTPException(status_code=401, detail="No email")
            
            user_whitelist = db.query(UserWhitelist).filter(UserWhitelist.email == email).one_or_none()
            if not user_whitelist:
                WHITELIST_VIOLATION.labels(email=email, provider=provider).inc()
                logger.warning(f"[AUTH] Non-whitelisted login attempt - Email: {email}, IP: {request.client.host}, Provider: {provider}")
                raise HTTPException(status_code=401, detail="Email not whitelisted")
        
        user = await create_or_update_user(db, provider, userinfo, token)
        
        user_data = {
            "sub": str(user.user_id),
            "auth_type": user.auth_type
        }

        AUTH_SUCCESS.labels(provider=provider).inc()
        logger.info(f"[AUTH] Successful login - User: {user.email}, IP: {request.client.host}, Provider: {provider}")

        temp_jwt = create_temp_jwt_token(user_data)
        frontend_redirect = f"{settings.BASE_URL}{settings.BASE_PATH}/login-success?temp_token={temp_jwt}"
        return RedirectResponse(frontend_redirect)

    except HTTPException:
        raise
    except Exception as e:
        AUTH_FAILURE.labels(provider=provider, reason="unexpected_error").inc()
        logger.error(f"[AUTH] Login error - Provider: {provider}, IP: {request.client.host}, Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later."
        )

@router.get("/login-success-redirect")
async def login_success_redirect(request: Request, response: Response):
    try:
        temp_token = request.query_params.get("temp_token")
        if not temp_token:
            raise HTTPException(status_code=400, detail="Missing temporary token")
            
        payload = jwt.decode(temp_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("token_type") != "temp":
            raise HTTPException(status_code=400, detail="Invalid token type")

        user_data = {
            "sub": payload["sub"],
        }

        redirect_html = f"""
        <html>
            <head>
                <meta http-equiv="refresh" content="0;url={settings.BASE_PATH}/login-success?temp_token={temp_token}">
            </head>
            <body>
                Redirecting...
            </body>
        </html>
        """
        return HTMLResponse(content=redirect_html)

    except Exception as e:
        logger.error(f"[AUTH] Error in login_success_redirect: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/validate-token")
async def validate_token(
    request: Request, 
    response: Response, 
    db: Session = Depends(get_db),
    memcache_client: aiomcache.Client = Depends(get_memcache_client)
    ):
    try:
        temp_token = request.query_params.get("temp_token")
        if not temp_token:
            AUTH_ERROR.labels(endpoint="validate_token", error_type="missing_token").inc()
            TOKEN_VALIDATION.labels(status="failure", reason="missing_token").inc()
            logger.error(f"[AUTH] Token validation failed - IP: {request.client.host}, Error: Missing temporary token")
            raise HTTPException(status_code=400, detail="Missing temporary token")
            
        try:
            payload = jwt.decode(temp_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        except JWTError as e:
            error_msg = str(e)
            error_type = "expired_token" if "expired" in error_msg.lower() else "invalid_token"
            
            AUTH_ERROR.labels(endpoint="validate_token", error_type=error_type).inc()
            TOKEN_VALIDATION.labels(status="failure", reason=error_type).inc()
            logger.error(f"[AUTH] Token validation failed - IP: {request.client.host}, Error: {error_msg}")
            
            if "expired" in error_msg.lower():
                raise HTTPException(status_code=401, detail="Token expired")
            raise HTTPException(status_code=401, detail="Invalid token format")

        if payload.get("token_type") != "temp":
            AUTH_ERROR.labels(endpoint="validate_token", error_type="wrong_token_type").inc()
            TOKEN_VALIDATION.labels(status="failure", reason="wrong_token_type").inc()
            logger.error(f"[AUTH] Token validation failed - IP: {request.client.host}, Error: Invalid token type")
            raise HTTPException(status_code=400, detail="Invalid token type")

        # Get user info from database to include in token
        user = db.query(User).filter(User.user_id == payload["sub"]).first()
        if not user:
            AUTH_ERROR.labels(endpoint="validate_token", error_type="user_not_found").inc()
            TOKEN_VALIDATION.labels(status="failure", reason="user_not_found").inc()
            logger.error(f"[AUTH] User not found during token validation - IP: {request.client.host}, User ID: {payload['sub']}")
            raise HTTPException(status_code=401, detail="User not found")

        user_data = {
            "sub": payload["sub"],
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
        }
        
        access_token, refresh_token = create_tokens(user_data)
        access_token_max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        refresh_token_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        access_token_expires = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        session_id = str(uuid.uuid4())
        
        # Set cookies
        response.set_cookie(
            key="access_token",
            value=access_token,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            httponly=True,
            samesite="lax",  # Must be 'lax' for sub-path routing between /assistant and /assistant/api
            domain=None,
            path=settings.COOKIE_PATH,
            max_age=access_token_max_age
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            httponly=True,
            samesite="lax",  # Must be 'lax' for sub-path routing between /assistant and /assistant/api
            domain=None,
            path=settings.COOKIE_PATH,
            max_age=refresh_token_max_age
        )

        response.set_cookie(
            key="session_id",
            value=session_id,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            httponly=True,
            samesite="lax",  # Must be 'lax' for sub-path routing between /assistant and /assistant/api
            domain=None,
            path=settings.COOKIE_PATH,
            max_age=settings.SESSION_ID_EXPIRE_MINUTES * 60
        )

        # Map session_id to user_id in the database and in cache
        session = UserSession(
            session_id=session_id, 
            user_id=user_data["sub"], 
            session_expires=datetime.utcnow() + timedelta(minutes=settings.SESSION_ID_EXPIRE_MINUTES),
            access_token_expires=access_token_expires,
            refresh_token_expires=refresh_token_expires,
            access_token=access_token,
            refresh_token=refresh_token
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        await memcache_client.set(session_id.encode(), json.dumps(user_data).encode())

        TOKEN_VALIDATION.labels(status="success", reason="valid_token").inc()
        logger.info(f"[AUTH] Token validation successful for user {user_data['sub']} from IP {request.client.host}")
        return {"status": "success"}

    except HTTPException:
        # Re-raise HTTP exceptions as they're already handled and counted
        raise
    except Exception as e:
        AUTH_ERROR.labels(endpoint="validate_token", error_type="unexpected_error").inc()
        TOKEN_VALIDATION.labels(status="failure", reason="unexpected_error").inc()
        logger.error(f"[AUTH] Token validation failed - IP: {request.client.host}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

class UserProfileResponse(BaseModel):
    user_id: str
    email: Optional[str]
    name: Optional[str]
    picture: Optional[str]

@router.get("/me", response_model=UserProfileResponse)
async def get_user_info(request: Request, db: Session = Depends(get_db)):
    try:
        # Get access token from cookie
        access_token = request.cookies.get("access_token")
        session_id = request.cookies.get("session_id")
        
        if not access_token:
            AUTH_ERROR.labels(endpoint="me", error_type="missing_token").inc()
            logger.warning(f"[AUTH] Access attempt without token - IP: {request.client.host}")
            raise HTTPException(status_code=401, detail="Not authenticated")

        if not session_id:
            AUTH_ERROR.labels(endpoint="me", error_type="missing_session").inc()
            logger.warning(f"[AUTH] Access attempt without session - IP: {request.client.host}")
            raise HTTPException(status_code=401, detail="No session")
    
        try:
            payload = jwt.decode(
                access_token, 
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )

            # Get full user data from database
            user = db.query(User).filter(User.user_id == payload["sub"]).first()
            if not user:
                AUTH_ERROR.labels(endpoint="me", error_type="user_not_found").inc()
                logger.error(f"[AUTH] User not found - IP: {request.client.host}, User ID: {payload['sub']}")
                raise HTTPException(status_code=401, detail="User not found")
            
            # Return comprehensive user profile
            return UserProfileResponse(
                user_id=str(user.user_id),
                email=user.email,
                name=user.name,
                picture=user.picture
            )
            
        except JWTError as e:
            # Handle all JWT-related errors with a single catch
            error_msg = str(e)
            error_type = "expired_token" if "expired" in error_msg.lower() else "invalid_token"
            
            AUTH_ERROR.labels(endpoint="me", error_type=error_type).inc()
            logger.error(f"[AUTH] Token validation failed - IP: {request.client.host}, Error: {error_msg}")
            
            if "expired" in error_msg.lower():
                raise HTTPException(status_code=401, detail="Token has expired")
            raise HTTPException(status_code=401, detail="Invalid token")
            
    except HTTPException:
        raise
    except Exception as e:
        AUTH_ERROR.labels(endpoint="me", error_type="unexpected_error").inc()
        logger.error(f"[AUTH] Unexpected error in /me endpoint - IP: {request.client.host}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path=settings.COOKIE_PATH)
    response.delete_cookie("refresh_token", path=settings.COOKIE_PATH)
    response.delete_cookie("session_id", path=settings.COOKIE_PATH)
    return {"message": "Logged out successfully"}

@router.post("/refresh")
async def refresh_token(
    request: Request, 
    response: Response,
    db: Session = Depends(get_db),
    memcache_client: aiomcache.Client = Depends(get_memcache_client)
):
    try:
        refresh_token = request.cookies.get("refresh_token")
        session_id = request.cookies.get("session_id")
        
        if not refresh_token or not session_id:
            AUTH_ERROR.labels(endpoint="refresh", error_type="missing_credentials").inc()
            TOKEN_REFRESH.labels(status="failure", reason="missing_credentials").inc()
            logger.error(f"[AUTH] Token refresh failed - IP: {request.client.host}, Error: Missing refresh token or session ID")
            raise HTTPException(status_code=401, detail="No refresh token or session ID")
        
        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_REFRESH_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
        except JWTError as e:
            error_msg = str(e)
            error_type = "expired_token" if "expired" in error_msg.lower() else "invalid_token"
            
            AUTH_ERROR.labels(endpoint="refresh", error_type=error_type).inc()
            TOKEN_REFRESH.labels(status="failure", reason=error_type).inc()
            logger.error(f"[AUTH] Token refresh failed - IP: {request.client.host}, Error: {error_msg}")
            
            if "expired" in error_msg.lower():
                raise HTTPException(status_code=401, detail="Token expired")
            raise HTTPException(status_code=401, detail="Invalid token format")

        # Get user data from database
        user = db.query(User).filter(User.user_id == payload["sub"]).first()
        if not user:
            AUTH_ERROR.labels(endpoint="refresh", error_type="user_not_found").inc()
            TOKEN_REFRESH.labels(status="failure", reason="user_not_found").inc()
            logger.error(f"[AUTH] Token refresh failed - IP: {request.client.host}, Error: User not found")
            raise HTTPException(status_code=401, detail="User not found")
        
        # Create new tokens
        user_data = {
            "sub": str(user.user_id),
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "auth_type": user.auth_type
        }
        
        access_token, new_refresh_token = create_tokens(user_data)
        
        # Calculate new expiry times
        access_token_expires = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        session_expires = datetime.utcnow() + timedelta(minutes=settings.SESSION_ID_EXPIRE_MINUTES)

        # Update session in database
        session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session")

        session.session_expires = session_expires
        session.access_token_expires = access_token_expires
        session.refresh_token_expires = refresh_token_expires
        session.access_token = access_token
        session.refresh_token = new_refresh_token
        db.commit()

        # Update session in cache
        cache_data = {
            "sub": str(user.user_id),
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
        }
        await memcache_client.set(
            session_id.encode(),
            json.dumps(cache_data).encode()
        )
        
        # Set new cookies
        response.set_cookie(
            key="access_token",
            value=access_token,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            httponly=True,
            samesite="lax",  # Must be 'lax' for sub-path routing between /assistant and /assistant/api
            path=settings.COOKIE_PATH,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            httponly=True,
            samesite="lax",  # Must be 'lax' for sub-path routing between /assistant and /assistant/api
            path=settings.COOKIE_PATH,
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )

        # Update session cookie expiry
        response.set_cookie(
            key="session_id",
            value=session_id,
            secure=False if settings.SYSTEM_MODE == "dev" else True,
            httponly=True,
            samesite="lax",  # Must be 'lax' for sub-path routing between /assistant and /assistant/api
            path=settings.COOKIE_PATH,
            max_age=settings.SESSION_ID_EXPIRE_MINUTES * 60
        )
        
        TOKEN_REFRESH.labels(status="success", reason="valid_token").inc()
        logger.info(f"[AUTH] Token refresh successful for user {user_data['sub']} from IP {request.client.host}")
        return {"status": "success"}
        
    except HTTPException:
        raise
    except Exception as e:
        AUTH_ERROR.labels(endpoint="refresh", error_type="unexpected_error").inc()
        TOKEN_REFRESH.labels(status="failure", reason="unexpected_error").inc()
        logger.error(f"[AUTH] Token refresh failed - IP: {request.client.host}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
