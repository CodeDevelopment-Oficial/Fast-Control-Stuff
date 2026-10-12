"""Endpoints CRUD del catálogo de herramientas (serial/UID único por pieza).

Cada endpoint está protegido por RBAC granular `herramientas:*`.
Flask consume estas rutas; nunca accede a la BD directamente.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession, require_permission
from app.schemas.tool import (
    CategoryCreate,
    CategoryOut,
    CountersOut,
    LocationCreate,
    LocationOut,
    ToolCreate,
    ToolDetailOut,
    ToolHoursAdd,
    ToolListOut,
    ToolMove,
    ToolOut,
    ToolStatusUpdate,
    ToolTypeCreate,
    ToolTypeOut,
    ToolTypeUpdate,
    ToolUpdate,
)
from app.services import tool_service as svc

router = APIRouter(prefix="/tools", tags=["herramientas"])

P_VIEW = Depends(require_permission("herramientas:view"))
P_CREATE = Depends(require_permission("herramientas:create"))
P_UPDATE = Depends(require_permission("herramientas:update"))
P_STATUS = Depends(require_permission("herramientas:update-status"))
P_DELETE = Depends(require_permission("herramientas:delete"))


# ---------------------------------------------------------------- mapeo

def _tool_out(t) -> ToolOut:
    remaining = None
    if t.life_hours is not None:
        remaining = max(float(t.life_hours) - float(t.used_hours), 0.0)
    return ToolOut(
        id=t.id, serial=t.serial, type_id=t.type_id,
        type_name=t.type.name if t.type else "", type_code=t.type.code if t.type else "",
        category_name=t.type.category.name if (t.type and t.type.category) else "",
        status=t.status, condition=t.condition,
        location_id=t.location_id, location_name=t.location.name if t.location else None,
        life_hours=float(t.life_hours) if t.life_hours is not None else None,
        used_hours=float(t.used_hours), remaining_hours=remaining,
        certificate_no=t.certificate_no, certificate_expires=t.certificate_expires,
        acquired_at=t.acquired_at, notes=t.notes,
        created_at=t.created_at, updated_at=t.updated_at,
    )


# ---------------------------------------------------------------- catálogos

@router.get("/categories", response_model=list[CategoryOut], dependencies=[P_VIEW])
def list_categories(db: DbSession):
    return svc.list_categories(db)


@router.post("/categories", response_model=CategoryOut, status_code=201, dependencies=[P_CREATE])
def create_category(body: CategoryCreate, db: DbSession, user: CurrentUser):
    return svc.create_category(db, user.id, body.name, body.description)


@router.get("/types", response_model=list[ToolTypeOut], dependencies=[P_VIEW])
def list_types(db: DbSession, category_id: int | None = Query(default=None)):
    from sqlalchemy import select
    from app.models.tool import ToolType
    stmt = select(ToolType).order_by(ToolType.code)
    if category_id:
        stmt = stmt.where(ToolType.category_id == category_id)
    return db.scalars(stmt).all()


@router.post("/types", response_model=ToolTypeOut, status_code=201, dependencies=[P_CREATE])
def create_type(body: ToolTypeCreate, db: DbSession, user: CurrentUser):
    return svc.create_type(db, user.id, body)


@router.patch("/types/{type_id}", response_model=ToolTypeOut, dependencies=[P_UPDATE])
def update_type(type_id: int, body: ToolTypeUpdate, db: DbSession, user: CurrentUser):
    return svc.update_type(db, user.id, type_id, body)


@router.get("/locations", response_model=list[LocationOut], dependencies=[P_VIEW])
def list_locations(db: DbSession):
    return svc.list_locations(db)


@router.post("/locations", response_model=LocationOut, status_code=201, dependencies=[P_CREATE])
def create_location(body: LocationCreate, db: DbSession, user: CurrentUser):
    return svc.create_location(db, user.id, body.name, body.address)


# ---------------------------------------------------------------- métricas

@router.get("/counters", response_model=CountersOut, dependencies=[P_VIEW])
def counters(db: DbSession):
    return svc.counters(db)


# ---------------------------------------------------------------- piezas
# OJO: rutas fijas ANTES de /{tool_id} para que "counters" no colisione.

@router.get("", response_model=ToolListOut, dependencies=[P_VIEW])
def list_tools(
    db: DbSession,
    q: str | None = Query(default=None, max_length=64, description="Serial o nombre/tipo"),
    status: str | None = Query(default=None),
    category_id: int | None = Query(default=None),
    type_id: int | None = Query(default=None),
    location_id: int | None = Query(default=None),
    cert_state: str | None = Query(default=None, pattern="^(vencida|por_vencer|sin_certificado)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    total, items = svc.list_tools(
        db, q=q, status=status, category_id=category_id, type_id=type_id,
        location_id=location_id, cert_state=cert_state, page=page, page_size=page_size,
    )
    return ToolListOut(total=total, page=page, page_size=page_size,
                       items=[_tool_out(t) for t in items])


@router.post("", response_model=ToolOut, status_code=201, dependencies=[P_CREATE])
def create_tool(body: ToolCreate, db: DbSession, user: CurrentUser):
    return _tool_out(svc.create_tool(db, user.id, body))


@router.get("/{tool_id}", response_model=ToolDetailOut, dependencies=[P_VIEW])
def tool_detail(tool_id: int, db: DbSession):
    tool, movements = svc.tool_detail(db, tool_id)
    base = _tool_out(tool).model_dump()
    base["movements"] = movements
    return ToolDetailOut(**base)


@router.patch("/{tool_id}", response_model=ToolOut, dependencies=[P_UPDATE])
def update_tool(tool_id: int, body: ToolUpdate, db: DbSession, user: CurrentUser):
    return _tool_out(svc.update_tool(db, user.id, tool_id, body))


@router.delete("/{tool_id}", status_code=204, dependencies=[P_DELETE])
def delete_tool(tool_id: int, db: DbSession, user: CurrentUser):
    svc.delete_tool(db, user.id, tool_id)


@router.post("/{tool_id}/status", response_model=ToolOut, dependencies=[P_STATUS])
def change_status(tool_id: int, body: ToolStatusUpdate, db: DbSession, user: CurrentUser):
    return _tool_out(svc.change_status(db, user.id, tool_id, body))


@router.post("/{tool_id}/hours", response_model=ToolOut, dependencies=[P_UPDATE])
def add_hours(tool_id: int, body: ToolHoursAdd, db: DbSession, user: CurrentUser):
    return _tool_out(svc.add_hours(db, user.id, tool_id, body))


@router.post("/{tool_id}/move", response_model=ToolOut, dependencies=[P_UPDATE])
def move_tool(tool_id: int, body: ToolMove, db: DbSession, user: CurrentUser):
    return _tool_out(svc.move_tool(db, user.id, tool_id, body))
