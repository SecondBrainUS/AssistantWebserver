from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Health check endpoint for AWS and other monitoring systems.
    Returns a 200 status code to indicate the service is healthy.
    """
    return JSONResponse(
        content={"status": "healthy"},
        status_code=200
    ) 