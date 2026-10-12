"""Schemas Pydantic v2 del dominio de autenticación."""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileOut(BaseModel):
    id: int
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    profile: ProfileOut


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class MessageOut(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strength(cls, v: str) -> str:
        checks = [len(v) >= 10, any(c.isdigit() for c in v), any(c.isupper() for c in v),
                  any(c.islower() for c in v), any(c in "!@#$%^&*()-_=+[]{};:,.<>?/" for c in v)]
        if sum(checks) < 4:
            raise ValueError(
                "La contraseña es demasiado débil: mínimo 10 caracteres con mayúsculas, "
                "minúsculas, dígitos y símbolos."
            )
        return v


class OkOut(BaseModel):
    ok: bool = True
