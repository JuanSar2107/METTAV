from flask import Blueprint, current_app, jsonify, request

from mi_app import gemini
from mi_app.extensions import db
from mi_app.security import limitador, respuesta_limite, usuario_actual
from mi_app.models import (
    ArticuloInventario,
    MovimientoInventario,
    RegistroAuditoria,
    Remision,
    SalidaIntegrada,
    Usuario,
)
from mi_app.models.inventory import GRUPOS_INVENTARIO
from mi_app.routes.reports import hora_colombia

asistente_bp = Blueprint("asistente", __name__, url_prefix="/api/asistente")

_MAX_PREGUNTA = 2000
_MAX_HISTORIAL = 10
# Límites del contexto: con mucha operación el texto enviado a Gemini no
# debe crecer sin control (cada consulta lo envía completo).
_MAX_ARTICULOS = 300
_MAX_MOVIMIENTOS = 60
_MAX_SALIDAS = 20
_MAX_REMISIONES = 20
_MAX_AUDITORIA = 30
_STOCK_BAJO = 5
# Evita que una sola cuenta agote la cuota de la API de Gemini.
_CONSULTAS_POR_MINUTO = 15


def _usuario_actual() -> Usuario | None:
    return usuario_actual()


def _detalles(pares) -> str:
    """'subpartida 8413.30.10.00; FOB USD 80.00' con solo los datos que existen."""
    return "; ".join(f"{nombre} {valor}" for nombre, valor in pares if valor not in (None, ""))


def _linea_articulo(a: ArticuloInventario) -> str:
    grupo = f"grupo {a.grupo}" if a.grupo else "sin grupo"
    linea = (
        f"- {a.codigo} | {a.nombre} | {grupo} | {a.categoria} | {a.ubicacion} | "
        f"stock {a.stock} {a.unidad} (más alto {a.stock_maximo})"
    )
    detalles = _detalles([
        ("interno", a.codigo_interno),
        ("marca", a.marca),
        ("serial", a.serial),
        ("subpartida", a.subpartida),
        ("FOB USD", a.valor_fob_usd),
        ("procedencia", a.procedencia),
        ("estado", a.estado),
        ("responsable", a.responsable),
        ("ingresó", a.fecha_ingreso),
        ("documento", a.documento_soporte),
        ("retiro", a.fecha_retiro),
        ("razón retiro", a.razon_retiro),
        ("cliente", a.cliente),
        ("servicio", a.tipo_servicio),
        ("estado del servicio", a.estado_servicio),
    ])
    return f"{linea} | {detalles}" if detalles else linea


def _linea_movimiento(m: MovimientoInventario) -> str:
    linea = (
        f"- {hora_colombia(m.fecha_hora)} | {m.tipo} | {m.cantidad} {m.unidad} | "
        f"{m.articulo} ({m.codigo_articulo}) | {m.empleado}"
    )
    detalles = _detalles([
        ("origen", m.origen),
        ("operación Sizfra", m.operacion_sizfra),
        ("formulario", m.formulario),
        ("salida integrada #", m.id_salida),
        ("rol", m.rol),
        ("remisión", m.remision.numero if m.remision else None),
        ("observaciones", m.observaciones),
    ])
    return f"{linea} | {detalles}" if detalles else linea


def _contexto_inventario(usuario: Usuario) -> str:
    """Resume en texto los datos del sistema que el usuario tiene permiso de ver.

    Cualquier usuario ve el inventario (igual que en el panel); el historial,
    las salidas integradas, las remisiones y la auditoría son de administradores.
    """
    articulos = (
        ArticuloInventario.query.order_by(ArticuloInventario.grupo, ArticuloInventario.codigo)
        .limit(_MAX_ARTICULOS)
        .all()
    )
    total_articulos = db.session.query(ArticuloInventario.id).count()
    lineas = [
        f"INVENTARIO ACTUAL ({total_articulos} artículos"
        + (f", se muestran los primeros {_MAX_ARTICULOS}" if total_articulos > _MAX_ARTICULOS else "")
        + "). Formato: código ZF | nombre | grupo | categoría | ubicación | stock | otros datos:"
    ]
    lineas += [_linea_articulo(a) for a in articulos] or ["- (sin artículos registrados)"]

    if not usuario.es_admin:
        return "\n".join(lineas)

    resumen = (
        db.session.query(
            ArticuloInventario.grupo,
            db.func.count(ArticuloInventario.id),
            db.func.sum(ArticuloInventario.stock),
        )
        .group_by(ArticuloInventario.grupo)
        .order_by(ArticuloInventario.grupo)
        .all()
    )
    lineas += ["", "RESUMEN POR GRUPO DE SIZFRA (grupo | artículos | unidades):"]
    lineas += [
        f"- {grupo or 'sin grupo'} {GRUPOS_INVENTARIO.get(grupo, '')} | {cantidad} | {unidades or 0}"
        for grupo, cantidad, unidades in resumen
    ]

    movimientos = (
        MovimientoInventario.query.order_by(MovimientoInventario.fecha_hora.desc(), MovimientoInventario.id.desc())
        .limit(_MAX_MOVIMIENTOS)
        .all()
    )
    lineas += ["", f"ÚLTIMOS MOVIMIENTOS (máximo {_MAX_MOVIMIENTOS}; hora Colombia | tipo | cantidad | artículo | empleado | otros datos):"]
    lineas += [_linea_movimiento(m) for m in movimientos] or ["- (sin movimientos registrados)"]

    salidas = (
        SalidaIntegrada.query.order_by(SalidaIntegrada.fecha_hora.desc()).limit(_MAX_SALIDAS).all()
    )
    lineas += ["", f"ÚLTIMAS {_MAX_SALIDAS} SALIDAS INTEGRADAS (partes integradas a un equipo):"]
    for s in salidas:
        lineas.append(
            f"- Salida #{s.id} | {hora_colombia(s.fecha_hora)} | {s.proceso} | equipo: {s.referencia} | "
            + _detalles([("operación Sizfra", s.operacion_sizfra), ("formulario", s.formulario),
                         ("empleado", s.empleado), ("observaciones", s.observaciones)])
        )
        lineas += [
            f"    {'equipo' if m.rol == 'Principal' else 'parte'}: {m.cantidad} {m.unidad} {m.articulo} ({m.codigo_articulo})"
            for m in s.movimientos
        ]
    if not salidas:
        lineas.append("- (sin salidas integradas)")

    remisiones = Remision.query.order_by(Remision.consecutivo.desc()).limit(_MAX_REMISIONES).all()
    lineas += ["", f"ÚLTIMAS {_MAX_REMISIONES} REMISIONES DE SALIDA (entregas a clientes):"]
    for r in remisiones:
        lineas.append(
            f"- {r.numero} | {r.fecha.isoformat()} | cliente {r.cliente_nombre} (NIT {r.cliente_nit}) | "
            + _detalles([("servicio", r.tipo_servicio), ("operación Sizfra", r.operacion_sizfra),
                         ("formulario", r.formulario), ("empleado", r.empleado), ("observaciones", r.observaciones)])
        )
        lineas += [
            f"    {l.cantidad} {l.unidad} {l.descripcion} ({l.codigo}) | estado del servicio {l.estado_servicio}"
            for l in r.lineas
        ]
    if not remisiones:
        lineas.append("- (sin remisiones)")

    auditoria = (
        RegistroAuditoria.query.order_by(RegistroAuditoria.fecha_hora.desc(), RegistroAuditoria.id.desc())
        .limit(_MAX_AUDITORIA)
        .all()
    )
    lineas += ["", f"ÚLTIMOS {_MAX_AUDITORIA} REGISTROS DE AUDITORÍA (crear, eliminar o actualizar artículos e importaciones):"]
    lineas += [
        f"- {hora_colombia(r.fecha_hora)} | {r.accion} | {r.codigo_articulo or '-'} | {r.empleado} | {r.detalle or ''}"
        for r in auditoria
    ] or ["- (sin registros)"]

    total_usuarios = db.session.query(Usuario.id_usuario).count()
    total_admins = db.session.query(Usuario.id_usuario).filter(Usuario.es_admin.is_(True)).count()
    lineas += ["", f"USUARIOS: {total_usuarios} registrados, {total_admins} administradores."]
    return "\n".join(lineas)


def _instrucciones(usuario: Usuario) -> str:
    rol = "administrador" if usuario.es_admin else "empleado"
    alcance = (
        "Tienes el inventario, el historial de movimientos, las salidas integradas, las remisiones y la auditoría."
        if usuario.es_admin
        else "Solo tienes el inventario actual; el historial, las salidas integradas, las remisiones y la "
             "auditoría son de administradores: si te preguntan por eso, explícalo amablemente."
    )
    return (
        "Eres el asistente virtual de METTAV Group SAS, empresa ubicada en la Zona Franca Permanente "
        "Intexzona (Cota, Cundinamarca) que repara, mantiene y fabrica maquinaria. "
        f"Hablas con '{usuario.nombre_completo or usuario.usuario}', que tiene rol de {rol}. {alcance}\n"
        "Conceptos del sistema:\n"
        "- Sizfra es el software oficial de la zona franca; cada ingreso o salida se registra allí como una "
        "operación (p. ej. 420) con un número de formulario.\n"
        "- El código ZF (ZF-...) es el que se registra en Sizfra; el código interno es de uso de METTAV.\n"
        "- Grupos de Sizfra: 001 activos de oficina, 002 equipos de bodega, 003 equipos operativos de bodega, "
        "004 mercancía de clientes que ingresa para prestar un servicio.\n"
        "- El valor FOB está en dólares (USD). La subpartida es la clasificación aduanera.\n"
        "- Una salida integrada da de baja en un solo registro un equipo y las partes que se le integraron "
        "(fabricación, reparación, mantenimiento u overhaul).\n"
        "- Una remisión de salida (REM-0001...) es la entrega de mercancía a un cliente; cada artículo queda "
        "con un estado del servicio: recibido, en servicio, terminado, entregado o cancelado.\n"
        "- 'Stock más alto' es solo informativo: los ingresos no tienen tope.\n"
        "Responde siempre en español, de forma breve y clara, en texto plano sin formato Markdown (puedes "
        "usar guiones para listas). Para preguntas sobre el inventario usa ÚNICAMENTE los datos de abajo; si "
        "algo no está en ellos, dilo en lugar de inventarlo, y si la respuesta puede estar en registros más "
        "antiguos de los que se muestran, sugiere la pestaña Reportes o la trazabilidad del artículo. "
        f"Considera stock bajo cuando sea {_STOCK_BAJO} o menos. Las fechas están en hora de Colombia. "
        "No puedes modificar el inventario: para ingresos, retiros, salidas integradas o remisiones el "
        "usuario debe usar el panel.\n\n"
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

    clave_limite = f"asistente:{usuario.id_usuario}"
    espera = limitador().espera(clave_limite, _CONSULTAS_POR_MINUTO, 60)
    if espera:
        return respuesta_limite(espera, "Has hecho muchas consultas seguidas.")
    limitador().registrar(clave_limite)

    mensajes = _historial_valido(datos.get("historial"))
    mensajes.append({"rol": "usuario", "texto": pregunta.strip()})
    try:
        respuesta = gemini.consultar_gemini(_instrucciones(usuario), mensajes)
    except gemini.GeminiError as error:
        current_app.logger.warning("Error del asistente Gemini: %s", error)
        return jsonify(error=str(error)), 502

    return jsonify(respuesta=respuesta)
