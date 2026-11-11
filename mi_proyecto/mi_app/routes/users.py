from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from mi_app import totp
from mi_app.validacion import correo_valido, mensaje_seguro
from mi_app.exportar import respuesta_excel, respuesta_pdf
from mi_app.extensions import db
from mi_app.security import (
    cerrar_sesion_actual,
    iniciar_sesion_usuario,
    ip_cliente,
    limitador,
    registrar_acceso,
    renovar_sello,
    respuesta_limite,
    revocar_sesiones_de,
    usuario_actual,
    validar_contrasena,
)
from mi_app.image_uploads import eliminar_imagen_subida, guardar_imagen
from mi_app.models import RegistroAcceso, SesionToken, Usuario

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api")

# Fuerza bruta: máximo de fallos por usuario+IP y por IP en la ventana.
_FALLOS_POR_USUARIO = 5
_FALLOS_POR_IP = 20
_VENTANA_LOGIN = 15 * 60
# Códigos de verificación en dos pasos: tope por usuario, sin importar la IP.
_FALLOS_2FA_POR_USUARIO = 10
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
        "rol": usuario.rol_clave,
        "totp_activo": bool(usuario.totp_activo),
        "nombre_completo": usuario.nombre_completo or "",
        "correo": usuario.correo or "",
        "numero_identidad": usuario.numero_identidad or "",
        "telefono": usuario.telefono or "",
        "direccion": usuario.direccion or "",
        "imagen_perfil": usuario.imagen_perfil or "",
    }


def _usuario_actual() -> Usuario | None:
    return usuario_actual()


def _secreto_totp(usuario: Usuario) -> str:
    return totp.revelar(usuario.totp_secreto, current_app.secret_key) or ""


def _validar_contrasena_nueva(contrasena, nombre: str | None = None) -> str | None:
    return validar_contrasena(contrasena, nombre)


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
    error_contrasena = _validar_contrasena_nueva(contrasena, nombre.strip())
    if error_contrasena is not None:
        return jsonify(error=error_contrasena), 400

    nombre = nombre.strip()
    if Usuario.query.filter_by(usuario=nombre).first() is not None:
        return jsonify(error="Ese usuario ya está registrado."), 409

    rol = datos.get("rol") or "empleado"
    if rol not in ("empleado", "auxiliar"):
        return jsonify(error="El rol debe ser empleado o auxiliar de inventarios."), 400

    # La contraseña la eligió el administrador: la persona debe cambiarla al entrar.
    usuario = Usuario(usuario=nombre, es_admin=False, es_auxiliar=rol == "auxiliar", cambio_requerido=True)
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
    formato = (request.args.get("formato") or "").lower()
    if formato not in ("xlsx", "pdf"):
        return jsonify(usuarios=[_respuesta_usuario(u) for u in usuarios])

    # Descarga: los mismos filtros que la pestaña Usuarios y Empleados (búsqueda y rol).
    texto = (request.args.get("q") or "").strip().lower()
    rol = (request.args.get("rol") or "").strip().lower()
    filtros = []
    if texto:
        filtros.append(f"búsqueda \"{request.args['q'].strip()}\"")
    nombres_rol = {"admin": "solo administradores", "auxiliar": "solo auxiliares de inventarios",
                   "empleado": "solo empleados / usuarios"}
    if rol in nombres_rol:
        filtros.append(nombres_rol[rol])

    def coincide(u: Usuario) -> bool:
        contenido = " ".join(v or "" for v in (
            u.usuario, u.nombre_completo, u.correo, u.numero_identidad, u.telefono,
        )).lower()
        return ((not texto or texto in contenido)
                and (rol not in nombres_rol or u.rol_clave == rol))

    filas = [[u.usuario, u.nombre_completo, u.rol_nombre, u.correo,
              u.numero_identidad, u.telefono, u.direccion] for u in usuarios if coincide(u)]
    encabezados = ["Usuario", "Nombre completo", "Rol", "Correo", "Número de identidad", "Teléfono", "Dirección"]
    if formato == "xlsx":
        return respuesta_excel("Usuarios", encabezados, filas, "usuarios-y-empleados")
    return respuesta_pdf(
        "Usuarios y empleados", encabezados, filas, "usuarios-y-empleados",
        anchos=[0.12, 0.18, 0.1, 0.18, 0.12, 0.11, 0.19],
        detalle=", ".join(filtros),
        generado_por=usuario_actual.nombre_completo or usuario_actual.usuario,
    )


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
        registrar_acceso("login_bloqueado", False, usuario=nombre, detalle="Demasiados intentos fallidos.")
        return respuesta_limite(espera, "Demasiados intentos fallidos.")

    usuario = Usuario.query.filter_by(usuario=nombre).first()
    if usuario is None:
        check_password_hash(_HASH_RELLENO, contrasena)
    if usuario is None or not usuario.verificar_contrasena(contrasena):
        limitador().registrar(clave_usuario)
        limitador().registrar(clave_ip)
        registrar_acceso("login_fallido", False, usuario=nombre,
                         id_usuario=usuario.id_usuario if usuario else None)
        return jsonify(error="Usuario o contraseña incorrectos."), 401

    if usuario.totp_activo:
        codigo = datos.get("codigo")
        if codigo in (None, ""):
            return jsonify(error="Escribe el código de verificación de tu aplicación.", requiere_2fa=True), 401
        clave_2fa = f"2fa:{usuario.id_usuario}"
        espera = max(
            limitador().espera(clave_2fa, _FALLOS_2FA_POR_USUARIO, _VENTANA_LOGIN),
            limitador().espera(clave_usuario, _FALLOS_POR_USUARIO, _VENTANA_LOGIN),
        )
        if espera:
            return respuesta_limite(espera, "Demasiados intentos fallidos.")
        paso = totp.verificar(_secreto_totp(usuario), codigo, usuario.totp_ultimo_paso)
        if paso is None:
            for clave in (clave_2fa, clave_usuario, clave_ip):
                limitador().registrar(clave)
            registrar_acceso("login_2fa_fallido", False, usuario=nombre, id_usuario=usuario.id_usuario)
            return jsonify(error="Código de verificación incorrecto.", requiere_2fa=True), 401
        usuario.totp_ultimo_paso = paso  # el mismo código no sirve dos veces
        db.session.commit()

    limitador().limpiar(clave_usuario)
    iniciar_sesion_usuario(usuario)
    return jsonify(usuario=_respuesta_usuario(usuario))


@usuarios_bp.post("/logout")
def cerrar_sesion():
    cerrar_sesion_actual()
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
    if correo and not correo_valido(correo):
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
            return jsonify(error=mensaje_seguro(error)), 400

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
        error_contrasena = _validar_contrasena_nueva(datos["contrasena"], usuario.usuario)
        if error_contrasena is not None:
            return jsonify(error=error_contrasena), 400
        if usuario.verificar_contrasena(datos["contrasena"]):
            return jsonify(error="La contraseña nueva debe ser distinta de la actual."), 400
        usuario.establecer_contrasena(datos["contrasena"])
        usuario.cambio_requerido = False

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="Ese usuario ya está registrado."), 409
    # La sesión actual sigue abierta; las demás se cierran si cambió la contraseña.
    if "contrasena" in datos:
        renovar_sello(usuario)
        registrar_acceso("cambio_contrasena", True, usuario=usuario.usuario, id_usuario=usuario.id_usuario)
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

    id_usuario = usuario.id_usuario
    nombre = usuario.usuario
    revocar_sesiones_de(id_usuario)
    SesionToken.query.filter_by(id_usuario=id_usuario).delete()
    db.session.delete(usuario)
    db.session.commit()
    registrar_acceso("cuenta_eliminada", True, usuario=nombre, id_usuario=id_usuario)
    cerrar_sesion_actual()
    return jsonify(mensaje="Cuenta eliminada.")


@usuarios_bp.post("/usuarios/me/2fa/iniciar")
def iniciar_2fa():
    """Genera un secreto TOTP para escanear en la app autenticadora; aún no exige código."""
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    datos = _leer_datos_json() or {}
    contrasena = datos.get("contrasena")
    if not isinstance(contrasena, str) or not usuario.verificar_contrasena(contrasena):
        return jsonify(error="Confirma tu contraseña en 'contrasena'."), 403
    if usuario.totp_activo:
        return jsonify(error="La verificación en dos pasos ya está activa."), 409
    secreto = totp.generar_secreto()
    usuario.totp_secreto = totp.proteger(secreto, current_app.secret_key)
    usuario.totp_ultimo_paso = None
    db.session.commit()
    return jsonify(secreto=secreto, uri=totp.uri_aprovisionamiento(secreto, usuario.usuario))


@usuarios_bp.post("/usuarios/me/2fa/activar")
def activar_2fa():
    """Activa la verificación en dos pasos si el código de la app autenticadora es correcto."""
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    datos = _leer_datos_json() or {}
    if usuario.totp_activo or not usuario.totp_secreto:
        return jsonify(error="Primero inicia la configuración de la verificación en dos pasos."), 409
    paso = totp.verificar(_secreto_totp(usuario), datos.get("codigo"))
    if paso is None:
        return jsonify(error="Código de verificación incorrecto."), 400
    usuario.totp_activo = True
    usuario.totp_ultimo_paso = paso
    db.session.commit()
    registrar_acceso("2fa_activada", True, usuario=usuario.usuario, id_usuario=usuario.id_usuario)
    return jsonify(mensaje="Verificación en dos pasos activada.")


@usuarios_bp.post("/usuarios/me/2fa/desactivar")
def desactivar_2fa():
    """Desactiva la verificación en dos pasos; pide la contraseña y un código vigente."""
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    datos = _leer_datos_json() or {}
    contrasena = datos.get("contrasena")
    if not isinstance(contrasena, str) or not usuario.verificar_contrasena(contrasena):
        return jsonify(error="Confirma tu contraseña en 'contrasena'."), 403
    if not usuario.totp_activo:
        return jsonify(error="La verificación en dos pasos no está activa."), 409
    if totp.verificar(_secreto_totp(usuario), datos.get("codigo"), usuario.totp_ultimo_paso) is None:
        return jsonify(error="Código de verificación incorrecto."), 400
    usuario.totp_activo = False
    usuario.totp_secreto = None
    usuario.totp_ultimo_paso = None
    db.session.commit()
    registrar_acceso("2fa_desactivada", True, usuario=usuario.usuario, id_usuario=usuario.id_usuario)
    return jsonify(mensaje="Verificación en dos pasos desactivada.")


@usuarios_bp.get("/accesos")
def listar_accesos():
    """Bitácora de accesos (inicios de sesión, fallos, bloqueos); solo administradores."""
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario.es_admin:
        return jsonify(error="Solo un administrador puede ver la bitácora de accesos."), 403
    try:
        limite = min(max(int(request.args.get("limite", 100)), 1), 500)
    except ValueError:
        limite = 100
    consulta = RegistroAcceso.query.order_by(RegistroAcceso.id.desc())
    filtro = (request.args.get("usuario") or "").strip()
    if filtro:
        consulta = consulta.filter(RegistroAcceso.usuario == filtro)
    if request.args.get("solo_fallos") == "1":
        consulta = consulta.filter(RegistroAcceso.exito.is_(False))
    return jsonify(accesos=[
        {
            "momento": r.momento.isoformat() + "Z",
            "evento": r.evento,
            "exito": r.exito,
            "usuario": r.usuario,
            "ip": r.ip,
            "agente": r.agente,
            "detalle": r.detalle,
        }
        for r in consulta.limit(limite).all()
    ])
