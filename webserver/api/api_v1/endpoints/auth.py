from fastapi import APIRouter, Depends, Request, Response, HTTPException
from authlib.integrations.starlette_client import OAuth
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from webserver.config import settings
from webserver.db.assistantdb.connection import get_db
from webserver.db.assistantdb.model import User, AuthGoogle
from datetime import datetime, timedelta
from jose import jwt
import uuid

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

def create_temp_jwt_token(user_data: dict):
    payload = {
        "sub": user_data["sub"],
        "email": user_data["email"],
        "exp": datetime.utcnow() + timedelta(minutes=5),  # Temporary token expiration
        "token_type": "temp"
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

@router.get("/{provider}/login")
async def login(provider: str, request: Request):
    if provider not in ["google"]:
        raise HTTPException(status_code=404, detail="Provider not supported")
    redirect_uri = f"{settings.BASE_URL}/api/v1/auth/{provider}/callback"
    if provider == "google":
        return await google.authorize_redirect(request, redirect_uri)
    else:
        return {"message": "Provider not supported"}

@router.get("/{provider}/callback")
async def callback(provider: str, request: Request, response: Response, db: Session = Depends(get_db)):
    if provider not in ["google"]:
        raise HTTPException(status_code=404, detail="Provider not supported")

    if provider == "google":
        token = await google.authorize_access_token(request)
        userinfo = token.get('userinfo')
    else:
        return {"message": "Provider not supported"}

    user = await create_or_update_user(db, provider, userinfo, token)

    user_data = {
        "sub": str(user.user_id),
        "email": user.email,
        "auth_type": user.auth_type,
        "picture": userinfo.get("picture"),
        "name": userinfo.get("name")
    }
    access_token, refresh_token = create_tokens(user_data)

    jwt_token = create_jwt_token(user, userinfo)

    # Redirect back to frontend with token
    frontend_redirect = f"{settings.BASE_URL}/login-success?token={jwt_token}"
    return RedirectResponse(frontend_redirect)

@router.get("/login-success-redirect")
async def login_success_redirect(request: Request, response: Response):

    access_token, refresh_token = create_tokens(user_data)
    response.set_cookie(
        key="access_token",
        value=access_token,
        # httponly=True,
        secure=False if settings.SYSTEM_MODE == "dev" else True,
        samesite="lax",
        domain=None,
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
        
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        # httponly=True,
        secure=False if settings.SYSTEM_MODE == "dev" else True,
        samesite="strict",  # "lax"
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    return RedirectResponse(f"{settings.BASE_URL}/login-success")

@router.post('/setcookie')
async def setcookie(request: Request, response: Response):
    response.set_cookie(
        key="ASD",
        value="ASDASDASD",
        httponly=True,
        secure=False if settings.SYSTEM_MODE == "dev" else True,
        samesite="strict",
        domain=None,
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return {"message": "Cookie set"}