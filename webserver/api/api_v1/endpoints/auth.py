from fastapi import APIRouter, Depends, Request, HTTPException
from authlib.integrations.starlette_client import OAuth
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from webserver.config import settings
from webserver.db.assistantdb.connection import get_db
from webserver.db.assistantdb.model import User, AuthGoogle
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
async def callback(provider: str, request: Request, db: Session = Depends(get_db)):
    if provider not in ["google"]:
        raise HTTPException(status_code=404, detail="Provider not supported")

    if provider == "google":
        token = await google.authorize_access_token(request)
        userinfo = token.get('userinfo')
    else:
        return {"message": "Provider not supported"}

    user = await create_or_update_user(db, provider, userinfo, token)
    jwt_token = create_jwt_token(user, userinfo)

    # Redirect back to frontend with token
    frontend_redirect = f"{settings.BASE_URL}/login-success?token={jwt_token}"
    return RedirectResponse(frontend_redirect)
