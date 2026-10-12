"""Controladores del catálogo de herramientas (MVC: Vista=templates/tools, Modelo=CoreClient/API).

Todas las rutas exigen sesión + permiso granular; los botones de la vista se
muestran con `permiso('herramientas:...')` y la API revalida el RBAC.
"""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.services.auth import (
    _current_core,
    ensure_fresh_access,
    has_permission,
    login_required,
    permission_required,
)
from app.services.core_client import CoreError

bp = Blueprint("tools", __name__, url_prefix="/herramientas")

STATUSES = ["disponible", "en_obra", "mantenimiento", "fuera_de_servicio", "baja"]
CONDITIONS = ["excelente", "buena", "regular", "dano"]


def _token() -> str | None:
    return ensure_fresh_access(_current_core())


@bp.get("/")
@login_required
def list_tools():
    if not has_permission("herramientas:view"):
        flash("No tienes permiso para ver el catálogo.", "danger")
        return redirect(url_for("auth.dashboard"))

    token = _token()
    params = {
        "q": request.args.get("q", "").strip(),
        "status": request.args.get("status", "").strip(),
        "category_id": request.args.get("category_id", "").strip(),
        "location_id": request.args.get("location_id", "").strip(),
        "cert_state": request.args.get("cert_state", "").strip(),
        "page": request.args.get("page", "1"),
        "page_size": "20",
    }
    core = _current_core()
    error = None
    data = {"total": 0, "items": [], "page": 1, "page_size": 20}
    categories, locations, counters = [], [], None
    try:
        data = core.tools_list(token, params)
        categories = core.categories(token)
        locations = core.locations(token)
        counters = core.counters(token)
    except CoreError as exc:
        error = exc.message

    pages = max((data["total"] + data["page_size"] - 1) // data["page_size"], 1)
    return render_template(
        "tools/list.html", data=data, pages=pages, filters=params,
        categories=categories, locations=locations, counters=counters,
        statuses=STATUSES, error=error,
    )


@bp.get("/nueva")
@permission_required("herramientas:create")
def new_tool():
    token = _token()
    core = _current_core()
    try:
        categories = core.categories(token)
        types = core.types(token)
        locations = core.locations(token)
    except CoreError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("tools.list_tools"))
    return render_template("tools/form.html", tool=None, categories=categories,
                           types=types, locations=locations, statuses=STATUSES,
                           conditions=CONDITIONS, mode="create")


@bp.post("/nueva")
@permission_required("herramientas:create")
def create_tool():
    body = _form_to_body()
    try:
        created = _current_core().tool_create(_token(), body)
    except CoreError as exc:
        return _revalidate_form(body, exc.message)
    flash(f"Herramienta {created['serial']} dada de alta correctamente.", "success")
    return redirect(url_for("tools.detail", tool_id=created["id"]))


@bp.get("/<int:tool_id>")
@login_required
def detail(tool_id: int):
    if not has_permission("herramientas:view"):
        flash("No tienes permiso para ver el catálogo.", "danger")
        return redirect(url_for("auth.dashboard"))
    token = _token()
    core = _current_core()
    try:
        tool = core.tool_get(token, tool_id)
        locations = core.locations(token)
    except CoreError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("tools.list_tools"))
    return render_template("tools/detail.html", tool=tool, locations=locations,
                           statuses=STATUSES)


@bp.get("/<int:tool_id>/editar")
@permission_required("herramientas:update")
def edit_tool(tool_id: int):
    token = _token()
    core = _current_core()
    try:
        tool = core.tool_get(token, tool_id)
        categories = core.categories(token)
        types = core.types(token)
        locations = core.locations(token)
    except CoreError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("tools.list_tools"))
    return render_template("tools/form.html", tool=tool, categories=categories,
                           types=types, locations=locations, statuses=STATUSES,
                           conditions=CONDITIONS, mode="edit")


@bp.post("/<int:tool_id>/editar")
@permission_required("herramientas:update")
def update_tool(tool_id: int):
    body = _form_to_body(partial=True)
    try:
        _current_core().tool_update(_token(), tool_id, body)
    except CoreError as exc:
        return _revalidate_form(body, exc.message, tool_id=tool_id)
    flash("Herramienta actualizada.", "success")
    return redirect(url_for("tools.detail", tool_id=tool_id))


# ---------------------------------------------------------------- acciones

@bp.post("/<int:tool_id>/estatus")
@permission_required("herramientas:update-status")
def change_status(tool_id: int):
    status = request.form.get("status", "")
    reason = request.form.get("reason", "")
    try:
        _current_core().tool_status(_token(), tool_id, status, reason)
    except CoreError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("tools.detail", tool_id=tool_id))
    flash(f"Estatus cambiado a «{status}».", "success")
    return redirect(url_for("tools.detail", tool_id=tool_id))


@bp.post("/<int:tool_id>/horas")
@permission_required("herramientas:update")
def add_hours(tool_id: int):
    try:
        hours = float(request.form.get("hours", ""))
    except ValueError:
        flash("Indica un número de horas válido.", "danger")
        return redirect(url_for("tools.detail", tool_id=tool_id))
    reason = request.form.get("reason") or None
    try:
        t = _current_core().tool_hours(_token(), tool_id, hours, reason)
    except CoreError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("tools.detail", tool_id=tool_id))
    flash(f"Horas registradas. Uso total: {t['used_hours']:g} h.", "success")
    return redirect(url_for("tools.detail", tool_id=tool_id))


@bp.post("/<int:tool_id>/mover")
@permission_required("herramientas:update")
def move_tool(tool_id: int):
    loc = request.form.get("to_location_id", "")
    if not loc.isdigit():
        flash("Selecciona una ubicación destino válida.", "danger")
        return redirect(url_for("tools.detail", tool_id=tool_id))
    reason = request.form.get("reason") or None
    try:
        _current_core().tool_move(_token(), tool_id, int(loc), reason)
    except CoreError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("tools.detail", tool_id=tool_id))
    flash("Herramienta movida a la nueva ubicación.", "success")
    return redirect(url_for("tools.detail", tool_id=tool_id))


@bp.post("/<int:tool_id>/eliminar")
@permission_required("herramientas:delete")
def delete_tool(tool_id: int):
    try:
        _current_core().tool_delete(_token(), tool_id)
    except CoreError as exc:
        flash(exc.message, "danger")
        return redirect(url_for("tools.detail", tool_id=tool_id))
    flash("Herramienta eliminada del catálogo.", "info")
    return redirect(url_for("tools.list_tools"))


# ---------------------------------------------------------------- helpers de formulario

def _form_to_body(partial: bool = False) -> dict:
    f = request.form
    body: dict = {
        "serial": f.get("serial", "").strip(),
        "type_id": int(f.get("type_id") or 0),
        "condition": f.get("condition") or "buena",
    }
    for key, field in (("location_id", "location_id"), ("life_hours", "life_hours"),
                       ("used_hours", "used_hours")):
        val = f.get(field, "").strip()
        if val != "":
            body[key] = float(val) if key.endswith("_hours") else int(val)
        elif not partial:
            body[key] = None if key == "location_id" else (0 if key == "used_hours" else None)
    for key in ("certificate_no",):
        if f.get(key, "").strip() or not partial:
            body[key] = f.get(key, "").strip() or None
    for key in ("certificate_expires", "acquired_at"):
        if f.get(key, "").strip():
            body[key] = f.get(key).strip()
        elif not partial:
            body[key] = None
    if f.get("notes", "").strip() or not partial:
        body["notes"] = f.get("notes", "").strip() or None
    return body


def _revalidate_form(body: dict, error: str, tool_id: int | None = None):
    """Re-renderiza el formulario conservando lo capturado ante errores de validación."""
    token = _token()
    core = _current_core()
    try:
        categories = core.categories(token)
        types = core.types(token)
        locations = core.locations(token)
    except CoreError:
        categories, types, locations = [], [], []
    tool = dict(body)
    tool["id"] = tool_id
    from datetime import date as _date
    for k in ("certificate_expires", "acquired_at"):
        v = tool.get(k)
        if isinstance(v, _date):
            tool[k] = v.isoformat()
    return render_template("tools/form.html", tool=tool, categories=categories,
                           types=types, locations=locations, statuses=STATUSES,
                           conditions=CONDITIONS,
                           mode="edit" if tool_id else "create", error=error)
