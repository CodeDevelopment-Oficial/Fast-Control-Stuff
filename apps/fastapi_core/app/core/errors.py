"""Manejadores de errores → respuestas HTTP con detalle estructurado {code, message}."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.auth_service import AuthError


class ApiError(Exception):
    """Error de negocio genérico (catálogo de herramientas, etc.)."""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthError)
    async def auth_error_handler(request: Request, exc: AuthError):
        return JSONResponse(
            status_code=exc.status,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )
