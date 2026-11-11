"""Recuperación de contraseña por correo electrónico.

1. La persona escribe su usuario o correo en /recuperar.
2. Si la cuenta tiene un correo registrado, recibe un enlace de un solo uso
   (/restablecer/<token>) que vale 30 minutos.
3. En ese enlace elige la contraseña nueva. Al guardarla se cierran todas sus sesiones.

El token se guarda solo como hash SHA-256: quien lea la base de datos no puede usarlo.
La respuesta de /api/recuperar es siempre la misma, exista o no la cuenta.
"""

import hashlib
import os
import secrets
import time

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy import or_

from mi_app import correo, totp
from mi_app.extensions import db
from mi_app.models import TokenRecuperacion, Usuario
from mi_app.security import (
    ip_cliente,
    limitador,
    registrar_acceso,
    respuesta_limite,
    revocar_sesiones_de,
    validar_contrasena,
)

recuperacion_bp = Blueprint("recuperacion", __name__)

_VIGENCIA = 30 * 60
_HORA = 3600
_SOLICITUDES_POR_IP = 10
_SOLICITUDES_POR_USUARIO = 3
_FALLOS_POR_IP = 20
_MENSAJE_GENERICO = (
    "Si la cuenta existe y tiene un correo registrado, te enviamos un enlace para elegir una contraseña nueva. "
    "Revisa también la carpeta de spam. El enlace vale 30 minutos."
)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _fila_valida(token: str) -> TokenRecuperacion | None:
    if not isinstance(token, str) or not 20 <= len(token) <= 128:
        return None
    fila = TokenRecuperacion.query.filter_by(hash_token=_hash(token)).first()
    if fila is None or fila.usado or fila.expira < time.time():
        return None
    return fila


def _url_base() -> str | None:
    """Dirección pública de la app. En producción debe venir de APP_URL (no del encabezado Host)."""
    configurada = (os.environ.get("APP_URL") or "").strip().rstrip("/")
    if configurada:
        return configurada
    if current_app.testing or request.host.split(":")[0] in ("localhost", "127.0.0.1"):
        return request.host_url.rstrip("/")
    return None


def _enviar_enlace(usuario: Usuario) -> None:
    base = _url_base()
    if base is None:
        current_app.logger.error(
            "No se envía el correo de recuperación: define APP_URL con la dirección pública de la app."
        )
        return
    ahora = int(time.time())
    TokenRecuperacion.query.filter_by(id_usuario=usuario.id_usuario, usado=False).update({"usado": True})
    TokenRecuperacion.query.filter(TokenRecuperacion.expira < ahora - 86400).delete()
    token = secrets.token_urlsafe(32)
    db.session.add(TokenRecuperacion(
        id_usuario=usuario.id_usuario, hash_token=_hash(token), creado=ahora, expira=ahora + _VIGENCIA, usado=False,
    ))
    db.session.commit()

    enlace = f"{base}/restablecer/{token}"
    if not correo.configurado():
        current_app.logger.warning("SMTP_HOST no está configurado: no se puede enviar el correo de recuperación.")
        if os.environ.get("MAIL_CONSOLA") == "1":  # solo para pruebas locales
            current_app.logger.warning("Enlace de recuperación (solo pruebas): %s", enlace)
        return
    correo.enviar_en_segundo_plano(
        usuario.correo,
        "Restablece tu contraseña de METTAV",
        f"Hola {usuario.nombre_completo or usuario.usuario},\n\n"
        "Recibimos una solicitud para cambiar la contraseña de tu cuenta de METTAV.\n"
        f"Abre este enlace para elegir una contraseña nueva (vale 30 minutos y solo se puede usar una vez):\n\n"
        f"{enlace}\n\n"
        "Si no fuiste tú, ignora este mensaje: tu contraseña actual sigue funcionando.\n",
    )


@recuperacion_bp.get("/recuperar")
def pagina_recuperar():
    """Pantalla donde se pide el enlace para restablecer la contraseña."""
    return render_template("recuperar.html")


@recuperacion_bp.get("/restablecer/<token>")
def pagina_restablecer(token: str):
    """Pantalla del enlace del correo, donde se elige la contraseña nueva."""
    fila = _fila_valida(token)
    usuario = db.session.get(Usuario, fila.id_usuario) if fila is not None else None
    respuesta = current_app.make_response(render_template(
        "restablecer.html",
        valido=usuario is not None,
        pide_codigo=bool(usuario and usuario.totp_activo),
        token=token if usuario is not None else "",
    ))
    respuesta.headers["Cache-Control"] = "no-store"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    return respuesta


@recuperacion_bp.post("/api/recuperar")
def solicitar_recuperacion():
    """Envía por correo un enlace de un solo uso para elegir una contraseña nueva."""
    datos = request.get_json(silent=True)
    identificador = datos.get("identificador") if isinstance(datos, dict) else None
    if not isinstance(identificador, str) or not identificador.strip() or len(identificador) > 254:
        return jsonify(error="Escribe tu usuario o tu correo."), 400
    identificador = identificador.strip()

    clave_ip = f"recuperar-ip:{ip_cliente()}"
    espera = limitador().espera(clave_ip, _SOLICITUDES_POR_IP, _HORA)
    if espera:
        return respuesta_limite(espera, "Has pedido demasiados enlaces.")
    limitador().registrar(clave_ip)

    usuario = Usuario.query.filter(
        or_(Usuario.usuario == identificador, Usuario.correo == identificador.lower())
    ).first()
    if usuario is not None and usuario.correo:
        clave_usuario = f"recuperar:{usuario.id_usuario}"
        if limitador().espera(clave_usuario, _SOLICITUDES_POR_USUARIO, _HORA) == 0:
            limitador().registrar(clave_usuario)
            _enviar_enlace(usuario)
            registrar_acceso("recuperacion_pedida", True, usuario=usuario.usuario, id_usuario=usuario.id_usuario)
    return jsonify(mensaje=_MENSAJE_GENERICO)


@recuperacion_bp.post("/api/restablecer")
def restablecer_contrasena():
    """Guarda la contraseña nueva usando el token del correo y cierra todas las sesiones."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="Envía un objeto JSON válido."), 400

    clave_ip = f"restablecer-ip:{ip_cliente()}"
    espera = limitador().espera(clave_ip, _FALLOS_POR_IP, 15 * 60)
    if espera:
        return respuesta_limite(espera, "Demasiados intentos fallidos.")

    fila = _fila_valida(datos.get("token"))
    usuario = db.session.get(Usuario, fila.id_usuario) if fila is not None else None
    if usuario is None:
        limitador().registrar(clave_ip)
        return jsonify(error="El enlace no es válido o ya venció. Pide uno nuevo."), 400

    if usuario.totp_activo:
        paso = totp.verificar(
            totp.revelar(usuario.totp_secreto, current_app.secret_key) or "", datos.get("codigo"), usuario.totp_ultimo_paso
        )
        if paso is None:
            limitador().registrar(clave_ip)
            return jsonify(error="Escribe el código de verificación de tu aplicación.", requiere_2fa=True), 401
        usuario.totp_ultimo_paso = paso

    contrasena = datos.get("contrasena")
    error = validar_contrasena(contrasena, usuario.usuario)
    if error is None and usuario.verificar_contrasena(contrasena):
        error = "La contraseña nueva debe ser distinta de la actual."
    if error is not None:
        return jsonify(error=error), 400

    usuario.establecer_contrasena(contrasena)
    usuario.cambio_requerido = False
    fila.usado = True
    db.session.commit()
    revocar_sesiones_de(usuario.id_usuario)
    registrar_acceso("contrasena_restablecida", True, usuario=usuario.usuario, id_usuario=usuario.id_usuario)

    if usuario.correo and correo.configurado():
        correo.enviar_en_segundo_plano(
            usuario.correo,
            "Tu contraseña de METTAV fue cambiada",
            "La contraseña de tu cuenta de METTAV se cambió con el enlace enviado a este correo.\n"
            "Si no fuiste tú, avisa de inmediato al administrador.\n",
        )
    return jsonify(mensaje="Contraseña actualizada. Ya puedes iniciar sesión.")
