"""Envío de correos por SMTP (por ejemplo, el enlace para restablecer la contraseña).

Se configura con variables de entorno:
    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM (por defecto SMTP_USER), SMTP_SEGURIDAD ("starttls" por defecto, "ssl" o "ninguna").
"""

import os
import smtplib
import threading
from email.message import EmailMessage

from flask import current_app


def configurado() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def enviar(destino: str, asunto: str, texto: str) -> None:
    """Envía un correo de texto. Lanza una excepción si el servidor SMTP falla."""
    servidor = os.environ["SMTP_HOST"]
    puerto = int(os.environ.get("SMTP_PORT") or 587)
    usuario = os.environ.get("SMTP_USER") or ""
    clave = os.environ.get("SMTP_PASSWORD") or ""
    remitente = os.environ.get("SMTP_FROM") or usuario
    seguridad = (os.environ.get("SMTP_SEGURIDAD") or "starttls").lower()

    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    mensaje.set_content(texto)

    if seguridad == "ssl":
        conexion = smtplib.SMTP_SSL(servidor, puerto, timeout=15)
    else:
        conexion = smtplib.SMTP(servidor, puerto, timeout=15)
    with conexion:
        if seguridad == "starttls":
            conexion.starttls()
        if usuario:
            conexion.login(usuario, clave)
        conexion.send_message(mensaje)


def enviar_en_segundo_plano(destino: str, asunto: str, texto: str) -> None:
    """Envía sin hacer esperar la respuesta (así no se nota si el usuario existe o no)."""
    app = current_app._get_current_object()

    def tarea():
        try:
            enviar(destino, asunto, texto)
        except Exception:  # noqa: BLE001
            app.logger.exception("No se pudo enviar el correo a un usuario.")

    if app.testing:
        tarea()
    else:
        threading.Thread(target=tarea, daemon=True).start()
