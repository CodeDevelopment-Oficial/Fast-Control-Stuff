"""Dependencias de FastAPI: usuario actual (JWT) y verificación RBAC por `recurso:acción`."""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import build_profile, resolve_permissions

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    request: Request,
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail={"code": "missing_token", "message": "Falta el token."})
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "token_expired", "message": "Token expirado."})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Token inválido."})

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Tipo de token inválido."})

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "invalid_user", "message": "Usuario no válido."})
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(code: str):
    """Dependencia factory: `Depends(require_permission('herramientas:export'))`.

    Úsala en cada endpoint para aplicar el RBAC granular a nivel de API.
    """

    def _checker(user: CurrentUser, db: DbSession) -> User:
        perms = set(resolve_permissions(db, user.id))
        if code not in perms and "*:*" not in perms:
            raise HTTPException(
                status_code=403,
                detail={"code": "forbidden", "message": f"Permiso requerido: {code}"},
            )
        return user

    return _checker


def me_payload(user: CurrentUser, db: DbSession) -> dict:
    return build_profile(db, user)
