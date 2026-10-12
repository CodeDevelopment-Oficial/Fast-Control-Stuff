"""Modelos del dominio de catálogo de herramientas (renta para perforación).

Reglas de negocio codificadas aquí:
- Cada pieza física se registra con un serial/UID único e inmutable.
- El estatus de la pieza es una máquina de estados controlada por la API
  (`herramientas:update-status`); las rentas lo modificarán en su módulo.
- La vida útil se expresa en horas; `used_hours` nunca excede `life_hours`
  sin que la herramienta quede marcada como agotada (validado en el servicio).
- Los movimientos de piezas se bitacorean además en audit_logs.
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import utcnow

# ---------------------------------------------------------------- catálogos

class ToolCategory(Base):
    """Familia de herramienta: TRB, Jarra, Estabilizador, Muela, Kelly, etc."""

    __tablename__ = "tool_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    types: Mapped[list["ToolType"]] = relationship(back_populates="category")


class ToolType(Base):
    """Modelo/catálogo dentro de una familia (p. ej. TRB 6-5/8 API Reg)."""

    __tablename__ = "tool_types"
    __table_args__ = (
        UniqueConstraint("category_id", "code", name="uq_tooltype_category_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("tool_categories.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)     # TRB-658-REG
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    size_inch: Mapped[str | None] = mapped_column(String(20))         # 6-5/8"
    material: Mapped[str | None] = mapped_column(String(80))          # AISI 4145H
    connection_top: Mapped[str | None] = mapped_column(String(80))    # NC50 box
    connection_bottom: Mapped[str | None] = mapped_column(String(80)) # NC50 pin
    default_life_hours: Mapped[float | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped[ToolCategory] = relationship(back_populates="types")
    tools: Mapped[list["Tool"]] = relationship(back_populates="type")


class Location(Base):
    """Ubicación física: patio, taller o base de operaciones."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------- pieza física

TOOL_STATUSES = ("disponible", "en_obra", "mantenimiento", "fuera_de_servicio", "baja")
CONDITIONS = ("excelente", "buena", "regular", "dano")


class Tool(Base):
    """Pieza individual identificada por serial/UID único."""

    __tablename__ = "tools"
    __table_args__ = (
        UniqueConstraint("serial", name="uq_tool_serial"),
        CheckConstraint(
            "status IN ('disponible','en_obra','mantenimiento','fuera_de_servicio','baja')",
            name="ck_tool_status",
        ),
        CheckConstraint(
            "condition IN ('excelente','buena','regular','dano')",
            name="ck_tool_condition",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    serial: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    type_id: Mapped[int] = mapped_column(
        ForeignKey("tool_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), default="disponible", nullable=False, index=True)
    condition: Mapped[str] = mapped_column(String(12), default="buena", nullable=False)

    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # Vida útil / horas de uso
    life_hours: Mapped[float | None] = mapped_column(Numeric(10, 2))   # límite; hereda del tipo si viene vacío
    used_hours: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    # Certificación (control simple; historial completo en módulo certificaciones)
    certificate_no: Mapped[str | None] = mapped_column(String(80))
    certificate_expires: Mapped[date | None] = mapped_column(Date, nullable=True)

    acquired_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    type: Mapped[ToolType] = relationship(back_populates="tools")
    location: Mapped[Location | None] = relationship()
    movements: Mapped[list["ToolMovement"]] = relationship(
        back_populates="tool", cascade="all, delete-orphan", order_by="ToolMovement.id.desc()"
    )


MOVEMENT_TYPES = ("alta", "movimiento", "status", "horas", "baja")


class ToolMovement(Base):
    """Bitácora de trazabilidad por pieza: quién movió qué, cuándo y por qué."""

    __tablename__ = "tool_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('alta','movimiento','status','horas','baja')",
            name="ck_movement_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    from_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    to_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str | None] = mapped_column(String(24))
    hours_delta: Mapped[float | None] = mapped_column(Numeric(10, 2))
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    tool: Mapped[Tool] = relationship(back_populates="movements")
