"""Medidas de seguridad compartidas por toda la aplicación.

- Clave secreta: nunca usa un valor por defecto conocido.
- Sesiones: cookie Lax, Secure en HTTPS, caducidad y sello que invalida las
  sesiones abiertas al cambiar la contraseña o borrar la cuenta.
- CSRF: rechaza peticiones que modifican datos si vienen de otro sitio.
- Cabeceras de seguridad (CSP, anti-clickjacking, nosniff, HSTS).
- Límite de intentos para el login y el asistente.
"""

import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import deque
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, current_app, has_request_context, jsonify, request, session
from flask.sessions import SecureCookieSessionInterface
from werkzeug.middleware.proxy_fix import ProxyFix

from mi_app.extensions import db

# Valores de ejemplo que aparecieron en el repositorio: si alguien los deja
# configurados, se tratan como si no hubiera clave.
_CLAVES_INSEGURAS = {
    "mettav-dev-key-2026",
    "cambia-esta-clave-en-produccion",
    "genera-aqui-una-clave-larga-y-aleatoria",
}
_METODOS_QUE_MODIFICAN = {"POST", "PUT", "PATCH", "DELETE"}

MIN_LARGO_CONTRASENA = 8

_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https://images.unsplash.com",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def resolver_clave_secreta(carpeta_instancia: Path) -> str:
    """Usa SECRET_KEY si es segura; si no, una clave aleatoria guardada en instance/.

    En Docker, instance/ es un volumen persistente, así que la clave generada
    sobrevive a los redespliegues y las sesiones no se cierran en cada uno.
    """
    clave = (os.environ.get("SECRET_KEY") or "").strip()
    if clave and clave not in _CLAVES_INSEGURAS:
        return clave

    archivo = carpeta_instancia / "secret_key"
    if archivo.exists():
        guardada = archivo.read_text(encoding="utf-8").strip()
        if guardada:
            return guardada
    nueva = secrets.token_hex(32)
    archivo.write_text(nueva, encoding="utf-8")
    try:
        archivo.chmod(0o600)
    except OSError:
        pass
    return nueva


class _SesionSegura(SecureCookieSessionInterface):
    """Marca la cookie como Secure siempre que la petición llegue por HTTPS."""

    def get_cookie_secure(self, app):
        return bool(app.config["SESSION_COOKIE_SECURE"]) or (
            has_request_context() and request.is_secure
        )


class LimitadorIntentos:
    """Cuenta eventos por clave en una ventana de tiempo (en memoria).

    Basta con memoria porque Gunicorn corre con un solo proceso.
    """

    def __init__(self):
        self._eventos: dict[str, deque] = {}
        self._candado = threading.Lock()

    def _vigentes(self, clave: str, ventana: float) -> deque:
        limite = time.monotonic() - ventana
        eventos = self._eventos.setdefault(clave, deque())
        while eventos and eventos[0] < limite:
            eventos.popleft()
        return eventos

    def espera(self, clave: str, maximo: int, ventana: float) -> int:
        """Segundos que faltan para poder intentarlo de nuevo (0 si se puede)."""
        with self._candado:
            eventos = self._vigentes(clave, ventana)
            if len(eventos) < maximo:
                return 0
            return max(1, int(eventos[0] + ventana - time.monotonic()) + 1)

    def registrar(self, clave: str) -> None:
        with self._candado:
            self._eventos.setdefault(clave, deque()).append(time.monotonic())

    def limpiar(self, clave: str) -> None:
        with self._candado:
            self._eventos.pop(clave, None)


def limitador() -> LimitadorIntentos:
    return current_app.extensions["mettav_limitador"]


def ip_cliente() -> str:
    return request.remote_addr or "desconocida"


def respuesta_limite(segundos: int, mensaje: str):
    minutos = -(-segundos // 60)
    respuesta = jsonify(error=f"{mensaje} Inténtalo de nuevo en {minutos} minuto(s).")
    respuesta.status_code = 429
    respuesta.headers["Retry-After"] = str(segundos)
    return respuesta


def _sello(contrasena_hash: str) -> str:
    """Huella de la contraseña actual guardada en la sesión (no revela el hash)."""
    return hmac.new(
        current_app.secret_key.encode("utf-8"), contrasena_hash.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]


def iniciar_sesion_usuario(usuario) -> None:
    session.clear()
    session.permanent = True
    session["id_usuario"] = usuario.id_usuario
    session["sello"] = _sello(usuario.contrasena_hash)


def renovar_sello(usuario) -> None:
    session["sello"] = _sello(usuario.contrasena_hash)


def usuario_actual():
    """Devuelve el usuario de la sesión, o None si no hay sesión válida.

    Si la contraseña cambió desde que se inició la sesión, la sesión deja de valer.
    """
    from mi_app.models import Usuario

    id_usuario = session.get("id_usuario")
    if not isinstance(id_usuario, int):
        return None
    usuario = db.session.get(Usuario, id_usuario)
    sello = session.get("sello")
    if usuario is None or not isinstance(sello, str) or not hmac.compare_digest(
        sello, _sello(usuario.contrasena_hash)
    ):
        return None
    return usuario


def _origen_permitido() -> bool:
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return False
    origen = request.headers.get("Origin") or request.headers.get("Referer")
    if origen is None:
        # Sin cabecera de origen (clientes que no son navegadores): la cookie
        # SameSite=Lax ya impide que un navegador la envíe desde otro sitio.
        return True
    return urlparse(origen).netloc == request.host


def configurar_seguridad(app: Flask) -> None:
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    app.session_interface = _SesionSegura()
    app.extensions["mettav_limitador"] = LimitadorIntentos()

    # Detrás del proxy de Coolify: confía en X-Forwarded-For/Proto/Host para
    # conocer la IP real del cliente y si la conexión es HTTPS.
    if os.environ.get("TRUST_PROXY") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.before_request
    def _proteger_csrf():
        if request.method in _METODOS_QUE_MODIFICAN and not _origen_permitido():
            return jsonify(error="Petición rechazada: origen no permitido."), 403
        return None

    @app.after_request
    def _cabeceras_seguridad(respuesta):
        cabeceras = respuesta.headers
        cabeceras.setdefault("Content-Security-Policy", _CSP)
        cabeceras.setdefault("X-Content-Type-Options", "nosniff")
        cabeceras.setdefault("X-Frame-Options", "DENY")
        cabeceras.setdefault("Referrer-Policy", "same-origin")
        cabeceras.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.is_secure:
            cabeceras.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.path.startswith("/api/") or request.path == "/dashboard":
            cabeceras.setdefault("Cache-Control", "no-store")
        return respuesta
