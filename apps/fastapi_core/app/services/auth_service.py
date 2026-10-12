"""Servicio de autenticación: verificación de credenciales, bloqueo y emisión de tokens."""
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, hash_password, needs_rehash, verify_password
from app.models.associations import user_roles
from app.models.user import AuditLog, PasswordResetToken, RefreshToken, Role, RolePermission, User, UserSession


class AuthError(Exception):
    """Error de autenticación con código de máquina legible por Flask."""

    def __init__(self, code: str, message: str, status: int = 401):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """Normalize DB datetimes to aware UTC.

    SQLite (desarrollo) devuelve datetimes *naive*; MySQL con
    DateTime(timezone=True) devuelve aware. Las comparaciones mixtas
    lanzan TypeError, así que normalizamos antes de comparar.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------- RBAC

def resolve_permissions(db: Session, user_id: int) -> list[str]:
    """Devuelve la lista efectiva de códigos de permiso del usuario.

    Resolución grant/deny: si algún rol otorga `*:*`, el usuario tiene todo.
    Un `deny` explícito elimina el permiso aunque otro rol lo otorgue.
    """
    from app.models.user import Permission

    grants: set[str] = set()
    denies: set[str] = set()
    stmt = (
        select(Permission.code, RolePermission.effect)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(user_roles, user_roles.c.role_id == RolePermission.role_id)
        .where(user_roles.c.user_id == user_id)
    )
    for code, effect in db.execute(stmt):
        (denies if effect == "deny" else grants).add(code)

    if "*:*" in grants:
        from app.core.permissions import all_permissions

        grants = set(all_permissions()) - {"*:*"}

    return sorted(grants - denies)


def get_user_roles(db: Session, user_id: int) -> list[str]:
    stmt = select(Role.name).join(user_roles, user_roles.c.role_id == Role.id).where(user_roles.c.user_id == user_id)
    return sorted(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------- Login

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email.lower().strip())).scalar_one_or_none()


def _audit(db: Session, user_id: int | None, action: str, detail: str | None, ip: str | None):
    db.add(AuditLog(user_id=user_id, action=action, detail=detail, ip_address=ip))


def authenticate(db: Session, email: str, password: str, ip: str | None = None, user_agent: str | None = None) -> dict:
    """Valida credenciales aplicando la política de bloqueo. Devuelve tokens + perfil."""
    user = get_user_by_email(db, email)

    # Usuario inexistente → misma respuesta que contraseña inválida (no enumeración)
    if user is None:
        _audit(db, None, "login.failed", f"email desconocido: {email}", ip)
        db.commit()
        raise AuthError("invalid_credentials", "Correo o contraseña incorrectos.")

    now = utcnow()
    locked_until = as_utc(user.locked_until)
    if locked_until and locked_until > now:
        mins = int((locked_until - now).total_seconds() // 60) + 1
        raise AuthError("account_locked", f"Cuenta bloqueada temporalmente. Intenta de nuevo en {mins} min.", 423)

    if not user.is_active:
        raise AuthError("inactive_account", "La cuenta está desactivada. Contacta al administrador.", 403)

    if not verify_password(user.password_hash, password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.max_failed_attempts:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_attempts = 0
            _audit(db, user.id, "login.locked", f"Bloqueo por {settings.lockout_minutes} min", ip)
        _audit(db, user.id, "login.failed", "contraseña incorrecta", ip)
        db.commit()
        remaining = max(settings.max_failed_attempts - user.failed_login_attempts, 0)
        msg = "Correo o contraseña incorrectos."
        if remaining:
            msg += f" Intentos restantes: {remaining}."
        raise AuthError("invalid_credentials", msg)

    # Éxito: rehash transparente si subieron los parámetros de Argon2
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    _audit(db, user.id, "login.success", None, ip)

    tokens = issue_tokens(db, user, ip=ip, user_agent=user_agent)
    db.commit()
    return {**tokens, "profile": build_profile(db, user)}


def issue_tokens(db: Session, user: User, ip: str | None, user_agent: str | None) -> dict:
    access = create_token(
        subject=str(user.id),
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_expires = utcnow() + timedelta(days=settings.refresh_token_expire_days)

    # Refresh con su propio jti almacenado para revocación server-side
    from app.core.security import jwt_id

    r_jti = jwt_id()
    refresh = create_token(
        subject=str(user.id),
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        extra={"sid": r_jti},
    )
    db.add(RefreshToken(jti=r_jti, user_id=user.id, expires_at=refresh_expires))
    db.add(UserSession(jti=r_jti, user_id=user.id, ip_address=ip, user_agent=user_agent, expires_at=refresh_expires))
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


def build_profile(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "roles": get_user_roles(db, user.id),
        "permissions": resolve_permissions(db, user.id),
    }


def refresh(db: Session, refresh_token: str) -> dict:
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AuthError("token_expired", "Tu sesión expiró. Inicia sesión de nuevo.")
    except jwt.PyJWTError:
        raise AuthError("invalid_token", "Token inválido.")

    if payload.get("type") != "refresh":
        raise AuthError("invalid_token", "Tipo de token inválido.")

    sid = payload.get("sid")
    stored = db.execute(select(RefreshToken).where(RefreshToken.jti == sid)).scalar_one_or_none()
    if stored is None or stored.revoked_at is not None or as_utc(stored.expires_at) < utcnow():
        raise AuthError("revoked_token", "La sesión fue cerrada. Inicia sesión de nuevo.")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("invalid_token", "Usuario no válido.")

    # Rotación: se revoca el usado y se emite uno nuevo
    stored.revoked_at = utcnow()
    tokens = issue_tokens(db, user, ip=None, user_agent=None)
    db.commit()
    return {**tokens, "profile": build_profile(db, user)}


def logout(db: Session, refresh_token: str) -> None:
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        sid = payload.get("sid")
    except jwt.PyJWTError:
        return
    for row in db.execute(select(RefreshToken).where(RefreshToken.jti == sid)):
        row.revoked_at = utcnow()
    db.commit()


# ---------------------------------------------------------------- Recuperación de contraseña

def create_password_reset(db: Session, email: str) -> tuple[User, str] | None:
    """Genera token de restablecimiento. Devuelve None si el correo no existe
    (la vista siempre responde igual para no enumerar usuarios)."""
    user = get_user_by_email(db, email)
    if user is None:
        return None
    from app.core.security import jwt_id

    jti = jwt_id()
    expires = utcnow() + timedelta(hours=settings.password_reset_url_ttl_hours)
    db.add(PasswordResetToken(jti=jti, user_id=user.id, expires_at=expires))
    token = create_token(subject=str(user.id), token_type="password_reset",
                         expires_delta=timedelta(hours=settings.password_reset_url_ttl_hours),
                         extra={"sid": jti})
    db.commit()
    return user, token


def consume_password_reset(db: Session, token: str, new_password: str) -> None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AuthError("reset_expired", "El enlace venció. Solicita uno nuevo.", 400)
    except jwt.PyJWTError:
        raise AuthError("reset_invalid", "Enlace inválido.", 400)

    if payload.get("type") != "password_reset":
        raise AuthError("reset_invalid", "Enlace inválido.", 400)

    rec = db.execute(select(PasswordResetToken).where(PasswordResetToken.jti == payload["sid"])).scalar_one_or_none()
    if rec is None or rec.used_at is not None:
        raise AuthError("reset_used", "Este enlace ya fue utilizado.", 400)

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise AuthError("reset_invalid", "Enlace inválido.", 400)

    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    rec.used_at = utcnow()
    # Cerrar todas las sesiones del usuario tras cambiar contraseña
    for rt in db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id,
                                                    RefreshToken.revoked_at.is_(None))):
        rt.revoked_at = utcnow()
    _audit(db, user.id, "password.reset", None, None)
    db.commit()
