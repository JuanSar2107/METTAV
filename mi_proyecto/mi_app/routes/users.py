from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
import re

from mi_app.extensions import db
from mi_app.security import (
    MIN_LARGO_CONTRASENA,
    iniciar_sesion_usuario,
    ip_cliente,
    limitador,
    renovar_sello,
    respuesta_limite,
    usuario_actual,
)
from mi_app.image_uploads import eliminar_imagen_subida, guardar_imagen
from mi_app.models import Usuario

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api")

# Fuerza bruta: máximo de fallos por usuario+IP y por IP en la ventana.
_FALLOS_POR_USUARIO = 5
_FALLOS_POR_IP = 20
_VENTANA_LOGIN = 15 * 60
# Hash de relleno para que un usuario inexistente tarde lo mismo que uno real.
_HASH_RELLENO = generate_password_hash("relleno-para-igualar-tiempos")


def _leer_datos_json() -> dict | None:
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else None


def _respuesta_usuario(usuario: Usuario):
    return {
        "id_usuario": usuario.id_usuario,
        "usuario": usuario.usuario,
        "es_admin": usuario.es_admin,
        "nombre_completo": usuario.nombre_completo or "",
        "correo": usuario.correo or "",
        "numero_identidad": usuario.numero_identidad or "",
        "telefono": usuario.telefono or "",
        "direccion": usuario.direccion or "",
        "imagen_perfil": usuario.imagen_perfil or "",
    }


def _usuario_actual() -> Usuario | None:
    return usuario_actual()


def _validar_contrasena_nueva(contrasena) -> str | None:
    if not isinstance(contrasena, str) or not MIN_LARGO_CONTRASENA <= len(contrasena) <= 256:
        return f"La contraseña debe tener entre {MIN_LARGO_CONTRASENA} y 256 caracteres."
    if contrasena.isdigit() or contrasena.isalpha():
        return "La contraseña debe combinar letras y números o símbolos."
    return None


@usuarios_bp.post("/usuarios")
def registrar_usuario():
    usuario_actual = _usuario_actual()
    if usuario_actual is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario_actual.es_admin:
        return jsonify(error="Solo un administrador puede crear usuarios."), 403

    datos = _leer_datos_json()
    if datos is None:
        return jsonify(error="Envía un objeto JSON válido."), 400

    nombre = datos.get("usuario")
    contrasena = datos.get("contrasena")
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 80:
        return jsonify(error="El campo 'usuario' es obligatorio."), 400
    error_contrasena = _validar_contrasena_nueva(contrasena)
    if error_contrasena is not None:
        return jsonify(error=error_contrasena), 400

    nombre = nombre.strip()
    if Usuario.query.filter_by(usuario=nombre).first() is not None:
        return jsonify(error="Ese usuario ya está registrado."), 409

    usuario = Usuario(usuario=nombre, es_admin=False)
    usuario.establecer_contrasena(contrasena)
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="Ese usuario ya está registrado."), 409

    return jsonify(usuario=_respuesta_usuario(usuario)), 201


@usuarios_bp.get("/usuarios")
def listar_usuarios():
    usuario_actual = _usuario_actual()
    if usuario_actual is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario_actual.es_admin:
        return jsonify(error="Solo un administrador puede ver la lista de usuarios."), 403

    usuarios = Usuario.query.order_by(Usuario.es_admin.desc(), Usuario.usuario.asc()).all()
    return jsonify(usuarios=[_respuesta_usuario(u) for u in usuarios])


@usuarios_bp.post("/login")
def iniciar_sesion():
    datos = _leer_datos_json()
    if datos is None:
        return jsonify(error="Envía un objeto JSON válido."), 400

    nombre = datos.get("usuario")
    contrasena = datos.get("contrasena")
    if not isinstance(nombre, str) or not isinstance(contrasena, str):
        return jsonify(error="Debes enviar usuario y contraseña."), 400

    nombre = nombre.strip()
    clave_ip = f"login-ip:{ip_cliente()}"
    clave_usuario = f"login:{ip_cliente()}:{nombre.lower()}"
    espera = max(
        limitador().espera(clave_usuario, _FALLOS_POR_USUARIO, _VENTANA_LOGIN),
        limitador().espera(clave_ip, _FALLOS_POR_IP, _VENTANA_LOGIN),
    )
    if espera:
        return respuesta_limite(espera, "Demasiados intentos fallidos.")

    usuario = Usuario.query.filter_by(usuario=nombre).first()
    if usuario is None:
        check_password_hash(_HASH_RELLENO, contrasena)
    if usuario is None or not usuario.verificar_contrasena(contrasena):
        limitador().registrar(clave_usuario)
        limitador().registrar(clave_ip)
        return jsonify(error="Usuario o contraseña incorrectos."), 401

    limitador().limpiar(clave_usuario)
    iniciar_sesion_usuario(usuario)
    return jsonify(usuario=_respuesta_usuario(usuario))


@usuarios_bp.post("/logout")
def cerrar_sesion():
    session.clear()
    return jsonify(mensaje="Sesión cerrada.")


@usuarios_bp.get("/usuarios/me")
def obtener_usuario_actual():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    return jsonify(usuario=_respuesta_usuario(usuario))


@usuarios_bp.post("/usuarios/me/perfil")
def actualizar_perfil():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    nombre_completo = request.form.get("nombre_completo", "").strip()
    correo = request.form.get("correo", "").strip().lower()
    numero_identidad = request.form.get("numero_identidad", "").strip()
    telefono = request.form.get("telefono", "").strip()
    direccion = request.form.get("direccion", "").strip()

    if len(nombre_completo) > 120 or len(correo) > 254:
        return jsonify(error="El nombre o correo supera el largo permitido."), 400
    if correo and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo) is None:
        return jsonify(error="Escribe un correo electrónico válido."), 400
    if len(numero_identidad) > 32 or len(telefono) > 32 or len(direccion) > 255:
        return jsonify(error="La identidad, teléfono o dirección supera el largo permitido."), 400

    if correo:
        existente = Usuario.query.filter_by(correo=correo).first()
        if existente is not None and existente.id_usuario != usuario.id_usuario:
            return jsonify(error="Ese correo ya está en uso."), 409
    if numero_identidad:
        existente = Usuario.query.filter_by(numero_identidad=numero_identidad).first()
        if existente is not None and existente.id_usuario != usuario.id_usuario:
            return jsonify(error="Ese número de identidad ya está en uso."), 409

    archivo_imagen = request.files.get("imagen_perfil")
    nueva_imagen_url = None
    ruta_nueva_imagen = None
    if archivo_imagen is not None and archivo_imagen.filename:
        try:
            nueva_imagen_url, ruta_nueva_imagen = guardar_imagen(archivo_imagen, "profiles")
        except ValueError as error:
            return jsonify(error=str(error)), 400

    imagen_anterior = usuario.imagen_perfil
    usuario.nombre_completo = nombre_completo or None
    usuario.correo = correo or None
    usuario.numero_identidad = numero_identidad or None
    usuario.telefono = telefono or None
    usuario.direccion = direccion or None
    if nueva_imagen_url is not None:
        usuario.imagen_perfil = nueva_imagen_url

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if ruta_nueva_imagen is not None:
            ruta_nueva_imagen.unlink(missing_ok=True)
        return jsonify(error="El correo o número de identidad ya está en uso."), 409

    if nueva_imagen_url is not None:
        eliminar_imagen_subida(imagen_anterior, "profiles")
    return jsonify(usuario=_respuesta_usuario(usuario))


@usuarios_bp.route("/usuarios/me", methods=["PUT", "PATCH"])
def actualizar_usuario_actual():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    datos = _leer_datos_json()
    if datos is None:
        return jsonify(error="Envía un objeto JSON válido."), 400
    if not any(campo in datos for campo in ("usuario", "contrasena")):
        return jsonify(error="Indica 'usuario' o 'contrasena' para actualizar."), 400

    if "usuario" in datos:
        nombre = datos["usuario"]
        if not isinstance(nombre, str) or not nombre.strip():
            return jsonify(error="El campo 'usuario' no puede estar vacío."), 400
        nombre = nombre.strip()
        existente = Usuario.query.filter_by(usuario=nombre).first()
        if existente is not None and existente.id_usuario != usuario.id_usuario:
            return jsonify(error="Ese usuario ya está registrado."), 409
        usuario.usuario = nombre

    if "contrasena" in datos:
        actual = datos.get("contrasena_actual")
        if not isinstance(actual, str) or not usuario.verificar_contrasena(actual):
            return jsonify(error="Para cambiar la contraseña indica la actual en 'contrasena_actual'."), 403
        error_contrasena = _validar_contrasena_nueva(datos["contrasena"])
        if error_contrasena is not None:
            return jsonify(error=error_contrasena), 400
        usuario.establecer_contrasena(datos["contrasena"])

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="Ese usuario ya está registrado."), 409
    # La sesión actual sigue abierta; las demás se cierran si cambió la contraseña.
    renovar_sello(usuario)
    return jsonify(usuario=_respuesta_usuario(usuario))


@usuarios_bp.delete("/usuarios/me")
def eliminar_usuario_actual():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    datos = _leer_datos_json() or {}
    contrasena = datos.get("contrasena")
    if not isinstance(contrasena, str) or not usuario.verificar_contrasena(contrasena):
        return jsonify(error="Confirma tu contraseña en 'contrasena' para eliminar la cuenta."), 403
    if usuario.es_admin and Usuario.query.filter_by(es_admin=True).count() <= 1:
        return jsonify(error="No puedes eliminar al único administrador."), 409

    db.session.delete(usuario)
    db.session.commit()
    session.clear()
    return jsonify(mensaje="Cuenta eliminada.")
