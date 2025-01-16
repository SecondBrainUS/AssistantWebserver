import logging
from fastapi import APIRouter, Query, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from webserver.config import settings
from typing import Optional
from webserver.api.dependencies import verify_access_token, get_session
from webserver.util.models import load_models, get_model_by_id

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("", 
    summary="Retrieve list of models",
    response_description="List of models",
    dependencies=[Depends(verify_access_token), Depends(get_session)])
async def get_models(
    request: Request,
    limit: Optional[int] = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of models to return (max 100)"
    ),
    offset: Optional[int] = Query(
        default=0,
        ge=0,
        description="Number of models to skip"
    )
) -> JSONResponse:
    """
    Retrieve list of models.
    
    Args:
        limit: Maximum number of models to return (default: 20, max: 100)
        offset: Number of models to skip for pagination (default: 0)
    
    Returns:
        JSONResponse containing:
        - models: List of models
    
    Raises:
        HTTPException: If database operation fails
    """
    models = load_models()
    return JSONResponse(content=models)