"""Schemas Pydantic v2 del catálogo de herramientas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.tool import CONDITIONS, TOOL_STATUSES


# ---------------------------------------------------------------- catálogos

class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=255)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    is_active: bool


class ToolTypeCreate(BaseModel):
    category_id: int
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=160)
    size_inch: str | None = Field(default=None, max_length=20)
    material: str | None = Field(default=None, max_length=80)
    connection_top: str | None = Field(default=None, max_length=80)
    connection_bottom: str | None = Field(default=None, max_length=80)
    default_life_hours: float | None = Field(default=None, gt=0)
    notes: str | None = None


class ToolTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    size_inch: str | None = None
    material: str | None = None
    connection_top: str | None = None
    connection_bottom: str | None = None
    default_life_hours: float | None = Field(default=None, gt=0)
    notes: str | None = None
    is_active: bool | None = None


class ToolTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_id: int
    code: str
    name: str
    size_inch: str | None
    material: str | None
    connection_top: str | None
    connection_bottom: str | None
    default_life_hours: float | None
    is_active: bool


class LocationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    address: str | None = Field(default=None, max_length=255)


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: str | None
    is_active: bool


# ---------------------------------------------------------------- piezas

class ToolCreate(BaseModel):
    serial: str = Field(min_length=3, max_length=64)
    type_id: int
    location_id: int | None = None
    condition: str = "buena"
    life_hours: float | None = Field(default=None, gt=0)
    used_hours: float = Field(default=0, ge=0)
    certificate_no: str | None = Field(default=None, max_length=80)
    certificate_expires: date | None = None
    acquired_at: date | None = None
    notes: str | None = None

    @field_validator("serial")
    @classmethod
    def normalize_serial(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) < 3:
            raise ValueError("El serial debe tener al menos 3 caracteres.")
        return v

    @field_validator("condition")
    @classmethod
    def valid_condition(cls, v: str) -> str:
        if v not in CONDITIONS:
            raise ValueError(f"Condición inválida. Válidas: {', '.join(CONDITIONS)}.")
        return v


class ToolUpdate(BaseModel):
    """Edición de datos administrativos. El estatus se cambia con endpoint propio."""

    type_id: int | None = None
    location_id: int | None = None
    condition: str | None = None
    life_hours: float | None = Field(default=None, gt=0)
    certificate_no: str | None = None
    certificate_expires: date | None = None
    acquired_at: date | None = None
    notes: str | None = None

    @field_validator("condition")
    @classmethod
    def valid_condition(cls, v: str | None) -> str | None:
        if v is not None and v not in CONDITIONS:
            raise ValueError(f"Condición inválida. Válidas: {', '.join(CONDITIONS)}.")
        return v


class ToolStatusUpdate(BaseModel):
    status: str
    reason: str = Field(min_length=5, max_length=255)

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in TOOL_STATUSES:
            raise ValueError(f"Estatus inválido. Válidos: {', '.join(TOOL_STATUSES)}.")
        return v


class ToolHoursAdd(BaseModel):
    hours: float = Field(gt=0, le=10000)
    reason: str | None = Field(default=None, max_length=255)


class ToolMove(BaseModel):
    to_location_id: int
    reason: str | None = Field(default=None, max_length=255)


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    movement_type: str
    from_status: str | None
    to_status: str | None
    from_location_id: int | None
    to_location_id: int | None
    hours_delta: float | None
    reason: str | None
    created_at: datetime
    user_id: int | None


class ToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    serial: str
    type_id: int
    type_name: str = ""
    type_code: str = ""
    category_name: str = ""
    status: str
    condition: str
    location_id: int | None
    location_name: str | None = None
    life_hours: float | None
    used_hours: float
    remaining_hours: float | None = None
    certificate_no: str | None
    certificate_expires: date | None
    acquired_at: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ToolDetailOut(ToolOut):
    movements: list[MovementOut] = []


class ToolListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ToolOut]


class CountersOut(BaseModel):
    total: int
    by_status: dict[str, int]
    cert_by_vencimiento: dict[str, int]  # vigente / por_vencer_90d / vencida / sin_certificado
    vida_agotada: int
