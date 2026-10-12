"""Manejadores de AuthError → respuestas HTTP con detalle estructurado {code, message}."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.auth_service import AuthError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthError)
    async def auth_error_handler(request: Request, exc: AuthError):
        return JSONResponse(
            status_code=exc.status,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )
