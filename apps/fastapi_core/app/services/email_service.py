"""Envío de correo transaccional (SMTP propio) para recuperación de contraseña."""
import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_password_reset_email(to_email: str, full_name: str, reset_link: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = "Restablece tu contraseña — Fast Control Stuff"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(
        f"Hola {full_name},\n\n"
        "Recibimos una solicitud para restablecer tu contraseña en Fast Control Stuff.\n\n"
        f"Abre el siguiente enlace (válido por {settings.password_reset_url_ttl_hours} hora):\n{reset_link}\n\n"
        "Si no solicitaste este cambio, ignora este correo; tu contraseña actual seguirá activa.\n\n"
        "— Equipo Fast Control Stuff"
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception:
        # En producción: loggear en bitácora estructurada; nunca revelar detalles al usuario.
        return False
