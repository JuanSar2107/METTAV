from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError
import re

from mi_app.extensions import db
from mi_app.image_uploads import eliminar_imagen_subida, guardar_imagen
from mi_app.models import Usuario

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api")


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
    id_usuario = session.get("id_usuario")
    if not isinstance(id_usuario, int):
        return None
    return db.session.get(Usuario, id_usuario)


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
    if not isinstance(contrasena, str) or len(contrasena) < 4 or len(contrasena) > 256:
        return jsonify(error="La contraseña debe tener entre 4 y 256 caracteres."), 400

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


@usuarios_bp.post("/login")
def iniciar_sesion():
    datos = _leer_datos_json()
    if datos is None:
        return jsonify(error="Envía un objeto JSON válido."), 400

    nombre = datos.get("usuario")
    contrasena = datos.get("contrasena")
    if not isinstance(nombre, str) or not isinstance(contrasena, str):
        return jsonify(error="Debes enviar usuario y contraseña."), 400

    usuario = Usuario.query.filter_by(usuario=nombre.strip()).first()
    if usuario is None or not usuario.verificar_contrasena(contrasena):
        return jsonify(error="Usuario o contraseña incorrectos."), 401

    session.clear()
    session["id_usuario"] = usuario.id_usuario
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
        contrasena = datos["contrasena"]
        if not isinstance(contrasena, str) or not contrasena:
            return jsonify(error="El campo 'contrasena' no puede estar vacío."), 400
        usuario.establecer_contrasena(contrasena)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="Ese usuario ya está registrado."), 409
    return jsonify(usuario=_respuesta_usuario(usuario))


@usuarios_bp.delete("/usuarios/me")
def eliminar_usuario_actual():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    db.session.delete(usuario)
    db.session.commit()
    session.clear()
    return jsonify(mensaje="Cuenta eliminada.")
