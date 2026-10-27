from flask import Blueprint, current_app, jsonify, request, session

from mi_app import gemini
from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario, Usuario

asistente_bp = Blueprint("asistente", __name__, url_prefix="/api/asistente")

_MAX_PREGUNTA = 2000
_MAX_HISTORIAL = 10
_MAX_ARTICULOS = 300
_MAX_MOVIMIENTOS = 40
_STOCK_BAJO = 5


def _usuario_actual() -> Usuario | None:
    id_usuario = session.get("id_usuario")
    if not isinstance(id_usuario, int):
        return None
    return db.session.get(Usuario, id_usuario)


def _contexto_inventario(usuario: Usuario) -> str:
    """Resume en texto los datos del sistema que el usuario tiene permiso de ver."""
    articulos = (
        ArticuloInventario.query.order_by(ArticuloInventario.categoria, ArticuloInventario.nombre)
        .limit(_MAX_ARTICULOS)
        .all()
    )
    lineas = ["INVENTARIO ACTUAL (código | nombre | categoría | stock/máximo | ubicación):"]
    lineas += [
        f"- {a.codigo} | {a.nombre} | {a.categoria} | {a.stock}/{a.stock_maximo} {a.unidad} | {a.ubicacion}"
        for a in articulos
    ] or ["- (sin artículos registrados)"]

    if usuario.es_admin:
        movimientos = (
            MovimientoInventario.query.order_by(MovimientoInventario.fecha_hora.desc())
            .limit(_MAX_MOVIMIENTOS)
            .all()
        )
        lineas.append("")
        lineas.append("ÚLTIMOS MOVIMIENTOS (fecha UTC | tipo | cantidad | artículo | empleado):")
        lineas += [
            f"- {m.fecha_hora:%Y-%m-%d %H:%M} | {m.tipo} | {m.cantidad} {m.unidad} | "
            f"{m.articulo} ({m.codigo_articulo}) | {m.empleado}"
            for m in movimientos
        ] or ["- (sin movimientos registrados)"]
        total_usuarios = db.session.query(Usuario.id_usuario).count()
        total_admins = db.session.query(Usuario.id_usuario).filter(Usuario.es_admin.is_(True)).count()
        lineas.append("")
        lineas.append(f"USUARIOS: {total_usuarios} registrados, {total_admins} administradores.")

    return "\n".join(lineas)


def _instrucciones(usuario: Usuario) -> str:
    rol = "administrador" if usuario.es_admin else "empleado"
    return (
        "Eres el asistente virtual de METTAV Group SAS, una empresa que gestiona un "
        "inventario de herramientas, equipos de protección y consumibles de taller. "
        f"Hablas con '{usuario.nombre_completo or usuario.usuario}', que tiene rol de {rol}. "
        "Responde siempre en español, de forma breve y clara, en texto plano sin formato "
        "Markdown (puedes usar guiones para listas). "
        "Para preguntas sobre el inventario usa ÚNICAMENTE los datos de abajo; si algo no "
        "está en ellos, dilo en lugar de inventarlo. Considera stock bajo cuando sea "
        f"{_STOCK_BAJO} o menos. Puedes ayudar también con dudas generales sobre el uso "
        "seguro de herramientas y buenas prácticas de almacén. No puedes modificar el "
        "inventario: para retirar o ingresar artículos el usuario debe usar el panel.\n\n"
        + _contexto_inventario(usuario)
    )


def _historial_valido(historial) -> list[dict]:
    if not isinstance(historial, list):
        return []
    mensajes = []
    for mensaje in historial[-_MAX_HISTORIAL:]:
        if not isinstance(mensaje, dict):
            continue
        rol = mensaje.get("rol")
        texto = mensaje.get("texto")
        if rol in ("usuario", "asistente") and isinstance(texto, str) and texto.strip():
            mensajes.append({"rol": rol, "texto": texto.strip()[:_MAX_PREGUNTA * 2]})
    # Gemini espera que la conversación empiece con un mensaje del usuario.
    while mensajes and mensajes[0]["rol"] != "usuario":
        mensajes.pop(0)
    return mensajes


@asistente_bp.post("/")
def consultar_asistente():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="Envía la consulta en formato JSON."), 400
    pregunta = datos.get("pregunta")
    if not isinstance(pregunta, str) or not pregunta.strip():
        return jsonify(error="Escribe una pregunta."), 400
    if len(pregunta) > _MAX_PREGUNTA:
        return jsonify(error=f"La pregunta no puede superar {_MAX_PREGUNTA} caracteres."), 400

    if not gemini.clave_configurada():
        return jsonify(error="El asistente no está configurado: falta GEMINI_API_KEY."), 503

    mensajes = _historial_valido(datos.get("historial"))
    mensajes.append({"rol": "usuario", "texto": pregunta.strip()})
    try:
        respuesta = gemini.consultar_gemini(_instrucciones(usuario), mensajes)
    except gemini.GeminiError as error:
        current_app.logger.warning("Error del asistente Gemini: %s", error)
        return jsonify(error=str(error)), 502

    return jsonify(respuesta=respuesta)
