from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from mi_app.extensions import db
from mi_app.models import Usuario

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api")


def _leer_datos_json() -> dict | None:
    datos = request.get_json(silent=True)
    return datos if isinstance(datos, dict) else None


def _respuesta_usuario(usuario: Usuario):
    return {
        "id_usuario": usuario.id_usuario,
        "usuario": usuario.usuario,
    }


def _usuario_actual() -> Usuario | None:
    id_usuario = session.get("id_usuario")
    if not isinstance(id_usuario, int):
        return None
    return db.session.get(Usuario, id_usuario)


@usuarios_bp.post("/usuarios")
def registrar_usuario():
    datos = _leer_datos_json()
    if datos is None:
        return jsonify(error="Envía un objeto JSON válido."), 400

    nombre = datos.get("usuario")
    contrasena = datos.get("contrasena")
    if not isinstance(nombre, str) or not nombre.strip():
        return jsonify(error="El campo 'usuario' es obligatorio."), 400
    if not isinstance(contrasena, str) or not contrasena:
        return jsonify(error="El campo 'contrasena' es obligatorio."), 400

    nombre = nombre.strip()
    if Usuario.query.filter_by(usuario=nombre).first() is not None:
        return jsonify(error="Ese usuario ya está registrado."), 409

    usuario = Usuario(usuario=nombre)
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
