"""Controladores de autenticación (C en MVC). Vistas en templates/auth/*.html."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.services.auth import bind_core, clear_session, get_core, has_permission, login_required, start_session
from app.services.core_client import CoreError

bp = Blueprint("auth", __name__)


@bp.app_context_processor
def inject_helpers():
    # Permite {% if permiso('inventario:create') %} en cualquier plantilla
    return {"permiso": has_permission}


@bp.get("/")
def index():
    if _logged_in():
        return redirect(url_for("auth.dashboard"))
    return redirect(url_for("auth.login"))


def _logged_in() -> bool:
    from flask import session

    return bool(session.get("user"))


# ---------------------------------------------------------------- LOGIN

@bp.route("/login", methods=["GET", "POST"])
def login():
    if _logged_in():
        return redirect(url_for("auth.dashboard"))

    error = None
    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        core = get_core(current_app)
        bind_core(core)
        try:
            result = core.login(email, password)
        except CoreError as exc:
            error = exc.message
        else:
            start_session(result, remember, current_app)
            return redirect(url_for("auth.dashboard"))

    return render_template("auth/login.html", error=error, email=email)


@bp.post("/logout")
@login_required
def logout():
    from flask import session

    core = get_core(current_app)
    try:
        core.logout(session.get("refresh_token", ""))
    except CoreError:
        pass  # aunque falle la revocación, limpiamos la sesión local
    clear_session()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------- DASHBOARD (placeholder protegido)

@bp.get("/dashboard")
@login_required
def dashboard():
    from flask import session

    return render_template("auth/dashboard.html", user=session["user"])


# ---------------------------------------------------------------- RECUPERAR CONTRASEÑA

@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    sent = False
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        core = get_core(current_app)
        bind_core(core)
        try:
            resp = core.forgot_password(email)
            sent = True
            flash(resp.get("message", ""), "success")
        except CoreError as exc:
            flash(exc.message, "danger")

    return render_template("auth/forgot_password.html", sent=sent)


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    token = request.args.get("token") or (request.form.get("token") if request.method == "POST" else None)
    error = None

    if request.method == "POST" and token:
        new_password = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        if new_password != confirm:
            error = "Las contraseñas no coinciden."
        else:
            core = get_core(current_app)
            bind_core(core)
            try:
                resp = core.reset_password(token, new_password)
                flash(resp.get("message", "Contraseña actualizada."), "success")
                return redirect(url_for("auth.login"))
            except CoreError as exc:
                error = exc.message

    return render_template("auth/reset_password.html", token=token, error=error)
