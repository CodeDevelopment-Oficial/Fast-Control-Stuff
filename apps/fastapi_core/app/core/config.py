from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central del core (leída de variables de entorno / .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # BD — FastAPI es el ÚNICO dueño de MySQL
    database_url: str = "sqlite:///./fcs_dev.db"  # fallback solo para desarrollo sin MySQL

    secret_key: str = "cambia-esto-por-un-secreto-largo-y-aleatorio"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    max_failed_attempts: int = 5
    lockout_minutes: int = 15

    # SMTP
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Fast Control Stuff <noreply@tudominio.com>"
    smtp_tls: bool = True
    password_reset_url_ttl_hours: int = 1

    cors_origins: str = "http://localhost:5000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
