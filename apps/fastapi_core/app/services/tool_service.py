"""Lógica de negocio del catálogo de herramientas.

Reglas aplicadas aquí (no en los endpoints):
- Serial/UID único por pieza (normalizado a mayúsculas).
- life_hours se hereda del tipo si no se especifica; used_hours no puede
  exceder life_hours al registrar horas.
- Cambios de estatus y movimientos quedan bitacoreados en tool_movements
  y audit_logs.
- 'baja' es terminal: no se editan ubicación/horas de una herramienta dada de baja.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ApiError
from app.models.tool import Location, Tool, ToolCategory, ToolMovement, ToolType
from app.schemas.tool import (
    ToolCreate,
    ToolHoursAdd,
    ToolMove,
    ToolStatusUpdate,
    ToolUpdate,
)


def _audit(db: Session, user_id: int, action: str, entity: str, entity_id, detail: str | None = None):
    from app.models.user import AuditLog

    db.add(AuditLog(user_id=user_id, action=action, entity=entity,
                    entity_id=str(entity_id), detail=detail))


# ---------------------------------------------------------------- catálogos

def create_category(db: Session, user_id: int, name: str, description: str | None):
    if db.scalar(select(ToolCategory).where(func.lower(ToolCategory.name) == name.lower())):
        raise ApiError(409, "duplicate", f"Ya existe la categoría '{name}'.")
    cat = ToolCategory(name=name.strip(), description=description)
    db.add(cat)
    db.flush()
    _audit(db, user_id, "category.create", "tool_category", cat.id, name)
    db.commit()
    db.refresh(cat)
    return cat


def list_categories(db: Session):
    return db.scalars(select(ToolCategory).order_by(ToolCategory.name)).all()


def create_type(db: Session, user_id: int, data: ToolTypeCreate):
    cat = db.get(ToolCategory, data.category_id)
    if cat is None:
        raise ApiError(404, "not_found", "La categoría indicada no existe.")
    dup = db.scalar(
        select(ToolType).where(ToolType.category_id == data.category_id,
                               func.upper(ToolType.code) == data.code.upper())
    )
    if dup:
        raise ApiError(409, "duplicate", f"El código '{data.code}' ya existe en esa categoría.")
    t = ToolType(**data.model_dump())
    db.add(t)
    db.flush()
    _audit(db, user_id, "type.create", "tool_type", t.id, t.code)
    db.commit()
    db.refresh(t)
    return t


def update_type(db: Session, user_id: int, type_id: int, data):
    t = db.get(ToolType, type_id)
    if t is None:
        raise ApiError(404, "not_found", "Tipo de herramienta no encontrado.")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.flush()
    _audit(db, user_id, "type.update", "tool_type", t.id)
    db.commit()
    db.refresh(t)
    return t


def create_location(db: Session, user_id: int, name: str, address: str | None):
    if db.scalar(select(Location).where(func.lower(Location.name) == name.lower())):
        raise ApiError(409, "duplicate", f"Ya existe la ubicación '{name}'.")
    loc = Location(name=name.strip(), address=address)
    db.add(loc)
    db.flush()
    _audit(db, user_id, "location.create", "location", loc.id, name)
    db.commit()
    db.refresh(loc)
    return loc


def list_locations(db: Session):
    return db.scalars(select(Location).order_by(Location.name)).all()


# ---------------------------------------------------------------- piezas

def _tool_query():
    return select(Tool).options(
        joinedload(Tool.type).joinedload(ToolType.category),
        joinedload(Tool.location),
    )


def get_tool_or_404(db: Session, tool_id: int) -> Tool:
    tool = db.scalar(_tool_query().where(Tool.id == tool_id))
    if tool is None:
        raise ApiError(404, "not_found", "Herramienta no encontrada.")
    return tool


def create_tool(db: Session, user_id: int, data: ToolCreate) -> Tool:
    serial = data.serial.strip().upper()
    if db.scalar(select(Tool).where(Tool.serial == serial)):
        raise ApiError(409, "serial_exists",
                       f"El serial '{serial}' ya está registrado. Cada pieza debe tener UID único.")
    tt = db.get(ToolType, data.type_id)
    if tt is None:
        raise ApiError(404, "not_found", "El tipo de herramienta indicado no existe.")
    if data.location_id is not None and db.get(Location, data.location_id) is None:
        raise ApiError(404, "not_found", "La ubicación indicada no existe.")
    if data.used_hours > 0 and data.life_hours and data.used_hours > float(data.life_hours):
        raise ApiError(422, "life_exceeded",
                       "Las horas usadas no pueden exceder la vida útil definida.")

    tool = Tool(
        serial=serial,
        type_id=data.type_id,
        location_id=data.location_id,
        condition=data.condition,
        life_hours=data.life_hours if data.life_hours is not None else (
            float(tt.default_life_hours) if tt.default_life_hours else None
        ),
        used_hours=data.used_hours,
        certificate_no=data.certificate_no,
        certificate_expires=data.certificate_expires,
        acquired_at=data.acquired_at,
        notes=data.notes,
        status="disponible",
    )
    db.add(tool)
    db.flush()
    db.add(ToolMovement(tool_id=tool.id, user_id=user_id, movement_type="alta",
                        to_location_id=tool.location_id, to_status="disponible",
                        reason="Alta en catálogo"))
    _audit(db, user_id, "tool.create", "tool", tool.id, f"serial={serial}")
    db.commit()
    return get_tool_or_404(db, tool.id)


def update_tool(db: Session, user_id: int, tool_id: int, data: ToolUpdate) -> Tool:
    tool = get_tool_or_404(db, tool_id)
    if tool.status == "baja":
        raise ApiError(422, "tool_decommissioned",
                       "No se puede editar una herramienta dada de baja.")
    payload = data.model_dump(exclude_unset=True)
    if "type_id" in payload and db.get(ToolType, payload["type_id"]) is None:
        raise ApiError(404, "not_found", "El tipo indicado no existe.")
    if "location_id" in payload and payload["location_id"] is not None \
            and db.get(Location, payload["location_id"]) is None:
        raise ApiError(404, "not_found", "La ubicación indicada no existe.")
    new_life = payload.get("life_hours")
    if new_life is not None and float(tool.used_hours) > float(new_life):
        raise ApiError(422, "life_exceeded",
                       "La nueva vida útil es menor que las horas ya registradas.")
    for k, v in payload.items():
        setattr(tool, k, v)
    db.flush()
    _audit(db, user_id, "tool.update", "tool", tool.id, f"serial={tool.serial}")
    db.commit()
    return get_tool_or_404(db, tool.id)


def change_status(db: Session, user_id: int, tool_id: int, data: ToolStatusUpdate) -> Tool:
    tool = get_tool_or_404(db, tool_id)
    if tool.status == "baja":
        raise ApiError(422, "tool_decommissioned",
                       "Una herramienta dada de baja no cambia de estatus.")
    if data.status == "baja" and tool.status != "fuera_de_servicio":
        raise ApiError(422, "invalid_transition",
                       "Solo herramientas 'fuera_de_servicio' pueden darse de baja.")
    old = tool.status
    tool.status = data.status
    db.add(ToolMovement(tool_id=tool.id, user_id=user_id, movement_type="status",
                        from_status=old, to_status=data.status, reason=data.reason))
    _audit(db, user_id, "tool.status", "tool", tool.id, f"{old} -> {data.status}: {data.reason}")
    db.commit()
    return get_tool_or_404(db, tool.id)


def add_hours(db: Session, user_id: int, tool_id: int, data: ToolHoursAdd) -> Tool:
    tool = get_tool_or_404(db, tool_id)
    if tool.status == "baja":
        raise ApiError(422, "tool_decommissioned", "No se registran horas a una herramienta de baja.")
    projected = float(tool.used_hours) + data.hours
    if tool.life_hours is not None and projected > float(tool.life_hours):
        raise ApiError(422, "life_exceeded",
                       f"Horas proyectadas ({projected:g}) exceden la vida útil "
                       f"({float(tool.life_hours):g}). Use 'fuera_de_servicio' o revalúe la vida útil.")
    tool.used_hours = projected
    db.add(ToolMovement(tool_id=tool.id, user_id=user_id, movement_type="horas",
                        hours_delta=data.hours, reason=data.reason))
    _audit(db, user_id, "tool.hours", "tool", tool.id, f"+{data.hours}h")
    db.commit()
    return get_tool_or_404(db, tool.id)


def move_tool(db: Session, user_id: int, tool_id: int, data: ToolMove) -> Tool:
    tool = get_tool_or_404(db, tool_id)
    if tool.status == "baja":
        raise ApiError(422, "tool_decommissioned", "No se mueve una herramienta de baja.")
    dest = db.get(Location, data.to_location_id)
    if dest is None:
        raise ApiError(404, "not_found", "La ubicación destino no existe.")
    origin = tool.location_id
    tool.location_id = dest.id
    db.add(ToolMovement(tool_id=tool.id, user_id=user_id, movement_type="movimiento",
                        from_location_id=origin, to_location_id=dest.id, reason=data.reason))
    _audit(db, user_id, "tool.move", "tool", tool.id, f"{origin} -> {dest.id}")
    db.commit()
    return get_tool_or_404(db, tool.id)


def delete_tool(db: Session, user_id: int, tool_id: int) -> None:
    """Eliminación física solo permitida si la pieza nunca se movió de su alta
    (evita borrar historial); de lo contrario, usar estatus 'baja'."""
    tool = get_tool_or_404(db, tool_id)
    n_movs = db.scalar(select(func.count(ToolMovement.id)).where(
        ToolMovement.tool_id == tool.id, ToolMovement.movement_type != "alta"))
    if n_movs:
        raise ApiError(422, "has_history",
                       "La pieza tiene historial de movimientos; dala de baja en su lugar.")
    _audit(db, user_id, "tool.delete", "tool", tool.id, f"serial={tool.serial}")
    db.delete(tool)
    db.commit()


# ---------------------------------------------------------------- consultas

def list_tools(
    db: Session, *, q: str | None, status: str | None, category_id: int | None,
    type_id: int | None, location_id: int | None, cert_state: str | None,
    page: int, page_size: int,
):
    stmt = _tool_query()
    conds = []
    if q:
        like = f"%{q.strip().upper()}%"
        conds.append(or_(Tool.serial.like(like), ToolType.code.ilike(f"%{q.strip()}%"),
                         ToolType.name.ilike(f"%{q.strip()}%")))
    if status:
        conds.append(Tool.status == status)
    if type_id:
        conds.append(Tool.type_id == type_id)
    elif category_id:
        conds.append(ToolType.category_id == category_id)
    if location_id:
        conds.append(Tool.location_id == location_id)
    if cert_state:
        today = date.today()
        if cert_state == "vencida":
            conds.append(Tool.certificate_expires.is_not(None), Tool.certificate_expires < today)
        elif cert_state == "por_vencer":
            conds.append(Tool.certificate_expires.is_not(None),
                         Tool.certificate_expires >= today,
                         Tool.certificate_expires <= today + timedelta(days=90))
        elif cert_state == "sin_certificado":
            conds.append(Tool.certificate_no.is_(None))
    if conds:
        stmt = stmt.where(*conds)

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.scalars(
        stmt.join(ToolType).order_by(Tool.serial).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return total, items


def tool_detail(db: Session, tool_id: int) -> tuple[Tool, list[ToolMovement]]:
    tool = get_tool_or_404(db, tool_id)
    movements = db.scalars(
        select(ToolMovement).where(ToolMovement.tool_id == tool.id)
        .order_by(ToolMovement.id.desc()).limit(200)
    ).all()
    return tool, movements


def counters(db: Session) -> dict:
    today = date.today()
    by_status = {
        r[0]: r[1] for r in db.execute(select(Tool.status, func.count(Tool.id)).group_by(Tool.status))
    }
    total = sum(by_status.values())
    cert_by_vencimiento = {
        "vigente": db.scalar(select(func.count(Tool.id)).where(
            Tool.certificate_expires.is_not(None), Tool.certificate_expires > today + timedelta(days=90))) or 0,
        "por_vencer_90d": db.scalar(select(func.count(Tool.id)).where(
            Tool.certificate_expires.is_not(None), Tool.certificate_expires >= today,
            Tool.certificate_expires <= today + timedelta(days=90))) or 0,
        "vencida": db.scalar(select(func.count(Tool.id)).where(
            Tool.certificate_expires.is_not(None), Tool.certificate_expires < today)) or 0,
        "sin_certificado": db.scalar(select(func.count(Tool.id)).where(
            Tool.certificate_no.is_(None))) or 0,
    }
    vida_agotada = db.scalar(
        select(func.count(Tool.id)).where(
            Tool.life_hours.is_not(None), Tool.used_hours >= Tool.life_hours)
    ) or 0
    return {"total": total, "by_status": by_status,
            "cert_by_vencimiento": cert_by_vencimiento, "vida_agotada": vida_agotada}
