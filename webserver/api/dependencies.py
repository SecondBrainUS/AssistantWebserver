from fastapi import Depends, HTTPException, Cookie
from jose import jwt, JWTError
from webserver.config import settings
from fastapi import Request

import logging
logger = logging.getLogger(__name__)


async def get_current_user(request: Request):
    """Dependency to get current user from access token"""
    logger.info("Checking current user")
    logger.info(f"Request host: {request.headers.get('host')}")
    logger.info(f"Request origin: {request.headers.get('origin')}")
    logger.info(f"Available cookies: {request.cookies}")
    
    access_token = request.cookies.get("access_token")
    logger.info(f"Access token present: {bool(access_token)}")
    
    if not access_token:
        logger.debug("No access token found in cookies")
        logger.debug(f"Available cookies: {request.cookies.keys()}")
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    try:
        payload = jwt.decode(
            access_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        logger.debug("Token decoded successfully")
        logger.debug(f"Token payload: {payload}")
        
        if payload.get("token_type") != "access":
            logger.debug("Invalid token type")
            raise HTTPException(status_code=401, detail="Invalid token type")
            
        return payload
        
    except JWTError as e:
        logger.debug(f"JWT decode error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")