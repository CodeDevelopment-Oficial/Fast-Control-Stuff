"""Autenticación y RBAC del lado Flask.

- La sesión del navegador vive en una cookie HTTP-only firmada por Flask.
- Los tokens JWT (access/refresh) se guardan dentro de la sesión de servidor
  (firmada, no accesible desde JS).
- `login_required` revalida el access token; si expiró, rota el refresh token.
- `permiso('recurso:accion')` habilita/muestra botones y menús en las vistas.
"""
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import redirect, session, url_for, flash

from app.services.core_client import CoreClient, CoreError

_core: CoreClient | None = None


def get_core(app) -> CoreClient:
    global _core
    if _core is None:
        _core = CoreClient(app.config["FASTAPI_BASE_URL"], app.config["REQUEST_TIMEOUT"])
    return _core


# ---------------------------------------------------------------- sesión

def start_session(core_result: dict, remember: bool, app) -> None:
    session.permanent = remember
    session["access_token"] = core_result["access_token"]
    session["refresh_token"] = core_result["refresh_token"]
    prof = core_result["profile"]
    session["user"] = {
        "id": prof["id"],
        "email": prof["email"],
        "full_name": prof["full_name"],
        "roles": prof["roles"],
    }
    session["permissions"] = sorted(set(prof["permissions"]))  # set no es serializable en cookie; se compara como lista
    session["access_exp"] = (
        datetime.now(timezone.utc) + timedelta(minutes=app.config.get("ACCESS_TOKEN_EXPIRE_MINUTES_VIEW", 15))
    ).isoformat()


def clear_session() -> None:
    session.clear()


def ensure_fresh_access(core: CoreClient) -> str | None:
    """Devuelve un access token válido, refrescando si es necesario."""
    token = session.get("access_token")
    exp = session.get("access_exp")
    if token and exp and datetime.fromisoformat(exp) > datetime.now(timezone.utc):
        return token
    rt = session.get("refresh_token")
    if not rt:
        return None
    try:
        result = core.refresh(rt)
    except CoreError:
        clear_session()
        return None
    session["access_token"] = result["access_token"]
    session["refresh_token"] = result["refresh_token"]
    session["permissions"] = sorted(set(result["profile"]["permissions"]))
    session["access_exp"] = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    return session["access_token"]


# ---------------------------------------------------------------- decoradores / helpers

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        if ensure_fresh_access(_current_core()) is None:
            flash("Tu sesión expiró. Inicia sesión nuevamente.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def permission_required(code: str):
    """Protege rutas completas con un permiso granular (además del check en la API)."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not has_permission(code):
                flash(f"No tienes permiso para acceder ({code}).", "danger")
                return redirect(url_for("auth.dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def has_permission(code: str) -> bool:
    """Uso en plantillas Jinja2: {% if permiso('herramientas:export') %} ... {% endif %}"""
    perms = session.get("permissions", set())
    return code in perms or "*:*" in perms


# El core client se inyecta una vez creada la app; guardamos referencia simple.
_CORE_REF: CoreClient | None = None


def bind_core(core: CoreClient) -> None:
    global _CORE_REF
    _CORE_REF = core


def _current_core() -> CoreClient:
    assert _CORE_REF is not None, "CoreClient no inicializado (create_app)"
    return _CORE_REF
