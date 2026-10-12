"""Configuración del cliente Flask (MVC). No accede a MySQL: todo pasa por la API."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret")

    FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000/api/v1")
    REQUEST_TIMEOUT = 10  # segundos hacia el core

    # Sesión Flask (cookie HTTP-only)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME_HOURS = int(os.getenv("REMEMBER_COOKIE_MAX_AGE_HOURS", "720"))

    # En producción (detrás de IIS con TLS): True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
