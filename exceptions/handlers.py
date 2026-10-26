import logging
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))


def _error(request: Request, status_code: int, code: str, message: str,
           details: Any = None, headers: dict[str, str] | None = None) -> JSONResponse:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "request_id": _request_id(request),
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        if exc.status_code >= 500:
            detail = "An internal error occurred"
        else:
            detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        codes = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN",
                 404: "NOT_FOUND", 409: "CONFLICT", 422: "UNPROCESSABLE_ENTITY",
                 429: "RATE_LIMITED"}
        return _error(request, exc.status_code, codes.get(exc.status_code, "HTTP_ERROR"),
                      detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # Exclude Pydantic's input/context fields; they may contain credentials or PII.
        details = [{"loc": list(item.get("loc", ())), "msg": item.get("msg", "Invalid value"),
                    "type": item.get("type", "value_error")} for item in exc.errors()]
        return _error(request, 422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError):
        logger.info("Database integrity conflict request_id=%s", _request_id(request))
        return _error(request, 409, "DATA_CONFLICT", "The request conflicts with existing data")

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError):
        logger.exception("Database operation failed request_id=%s", _request_id(request))
        return _error(request, 500, "DATABASE_ERROR", "An internal error occurred")

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled request error request_id=%s", _request_id(request))
        return _error(request, 500, "INTERNAL_ERROR", "An internal error occurred")
