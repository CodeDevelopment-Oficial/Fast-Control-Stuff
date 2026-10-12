"""Tabla puente user_roles (secundaria declarada explícitamente)."""
from sqlalchemy import Column, ForeignKey, Integer, Table

from app.core.database import Base
from app.models.user import User  # noqa: F401  (asegura que las tablas base existan al declarar esta)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)
