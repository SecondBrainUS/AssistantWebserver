from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Any, Dict, Union, Optional

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseHTTPException(HTTPException):
    chained_exception: Optional[Exception]

    def __init__(
        self,
        status_code: int,
        detail: str,
        chained_exception: Optional[Exception] = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.chained_exception = chained_exception


def load_exception_handlers(app):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        logger.error("Custom Error: %s", exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": exc.body, "content": "YES"},
        )

    @app.exception_handler(BaseHTTPException)
    async def http_exception_handler(request: Request, exc: BaseHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error("Generic Exception: %s", str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )
