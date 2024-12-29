from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt
from webserver.config import settings

class VerifyAccessTokenMiddleware(BaseHTTPMiddleware):
    """ Middleware to verify access token from cookies """
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
    async def dispatch(self, request: Request, call_next):
        session_id = request.cookies.get("session_id")
        if not session_id:
            return JSONResponse(status_code=401, content={"detail": "No session ID"})
        return await call_next(request)

    def check_cache(self, session_id: str) -> dict:
        # TODO: check if session_id is in cache
        pass

    def check_db(self, session_id: str):
        # TODO: check if session_id is in db
        pass

    def check_access_token(self, access_token: str):
        # TODO: check if access_token is in db
        pass

