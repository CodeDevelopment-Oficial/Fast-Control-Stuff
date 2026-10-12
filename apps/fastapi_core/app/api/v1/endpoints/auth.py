"""Endpoints de autenticación consumidos por el cliente Flask (MVC).

Nota de seguridad: la API NUNCA envía cookies al navegador. Flask guarda las
sesiones HTTP-only; los tokens viajan solo por el canal interno Flask↔FastAPI.
"""
from fastapi import APIRouter, Request

from app.core.deps import CurrentUser, DbSession, me_payload
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageOut,
    OkOut,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPairOut,
)
from app.services import auth_service
from app.services.email_service import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    # IIS como reverse proxy puede enviar X-Forwarded-For
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenPairOut)
def login(body: LoginRequest, request: Request, db: DbSession):
    result = auth_service.authenticate(
        db,
        email=body.email,
        password=body.password,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return result


@router.post("/refresh", response_model=TokenPairOut)
def refresh(body: RefreshRequest, db: DbSession):
    return auth_service.refresh(db, body.refresh_token)


@router.post("/logout", response_model=OkOut)
def logout(body: LogoutRequest, db: DbSession):
    auth_service.logout(db, body.refresh_token)
    return OkOut()


@router.get("/me")
def me(user: CurrentUser, db: DbSession):
    return me_payload(user, db)


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(body: ForgotPasswordRequest, request: Request, db: DbSession):
    generic = "Si el correo existe, recibiste un enlace de recuperación."
    result = auth_service.create_password_reset(db, body.email)
    if result is not None:
        user, token = result
        # Flask monta la página /reset-password; el enlace apunta al cliente MVC.
        # En producción IIS debe enviar X-Forwarded-Host con el dominio público de Flask.
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:5000"
        scheme = request.headers.get("x-forwarded-proto", "http")
        link = f"{scheme}://{host}/auth/reset-password?token={token}"
        send_password_reset_email(user.email, user.full_name, link)
    return MessageOut(message=generic)


@router.post("/reset-password", response_model=MessageOut)
def reset_password(body: ResetPasswordRequest, db: DbSession):
    auth_service.consume_password_reset(db, body.token, body.new_password)
    return MessageOut(message="Tu contraseña fue actualizada. Ya puedes iniciar sesión.")
