"""Remisiones de salida (R8): entrega de mercancía a un cliente.

Una remisión descuenta del stock cada línea (como un retiro), deja el
movimiento en el historial, actualiza el estado del servicio del artículo y
se puede imprimir o guardar como PDF desde /remisiones/<id>.
"""

import re
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario, Remision, RemisionLinea
from mi_app.models.inventory import ESTADOS_SERVICIO, ORIGEN_REMISION, TIPOS_SERVICIO
from mi_app.routes.inventory import datos_sizfra, descontar_stock
from mi_app.security import usuario_actual

remisiones_bp = Blueprint("remisiones", __name__)

# Datos de METTAV que encabezan la remisión (tomados de la remisión en Excel).
EMPRESA = {
    "nombre": "METTAV GROUP S.A.S.",
    "nit": "901.982.258-4",
    "direccion": "Zona Franca Permanente Intexzona – Bodega 57",
    "ciudad": "Cota – Cundinamarca",
}

_HORA_COLOMBIA = timezone(timedelta(hours=-5))
_RE_NIT = re.compile(r"^[0-9][0-9.\- ]{3,30}$")
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LIMITES = {
    "cliente_nombre": 160, "cliente_nit": 32, "contacto": 120, "telefono": 60, "email": 160,
    "documento_entrega": 120, "observaciones": 2000,
}


def _texto(datos, campo) -> str:
    return str(datos.get(campo) or "").strip()


@remisiones_bp.post("/api/remisiones")
def crear_remision():
    """Crea la remisión y da de baja la mercancía en un solo paso.

    JSON: {"cliente_nombre", "cliente_nit", "contacto", "telefono", "email", "tipo_servicio",
    "documento_entrega", "observaciones", "operacion_sizfra", "formulario", "fecha",
    "lineas": [{"id", "cantidad", "estado_servicio"}, ...]}.
    """
    usuario = usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="Envía los datos de la remisión en formato JSON."), 400

    campos = {campo: _texto(datos, campo) for campo in _LIMITES}
    for campo, limite in _LIMITES.items():
        if len(campos[campo]) > limite:
            return jsonify(error=f"El campo {campo.replace('_', ' ')} no puede superar {limite} caracteres."), 400
    if not campos["cliente_nombre"]:
        return jsonify(error="Indica el nombre del cliente."), 400
    if not _RE_NIT.match(campos["cliente_nit"]):
        return jsonify(error="Indica el NIT o la cédula del cliente, por ejemplo 900.059.427-0."), 400
    if campos["email"] and not _RE_EMAIL.match(campos["email"]):
        return jsonify(error="El correo del cliente no es válido."), 400
    tipo_servicio = _texto(datos, "tipo_servicio")
    if tipo_servicio and tipo_servicio not in TIPOS_SERVICIO:
        return jsonify(error="El tipo de servicio debe ser: " + ", ".join(TIPOS_SERVICIO) + "."), 400
    try:
        sizfra = datos_sizfra(datos)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    try:
        fecha = date.fromisoformat(_texto(datos, "fecha")) if _texto(datos, "fecha") else datetime.now(_HORA_COLOMBIA).date()
    except ValueError:
        return jsonify(error="La fecha debe tener el formato AAAA-MM-DD."), 400

    lineas = datos.get("lineas")
    if not isinstance(lineas, list) or not lineas:
        return jsonify(error="Agrega al menos un artículo a la remisión."), 400
    if len(lineas) > 100:
        return jsonify(error="Una remisión admite máximo 100 líneas."), 400
    for linea in lineas:
        if not isinstance(linea, dict) or not isinstance(linea.get("id"), int) or isinstance(linea.get("id"), bool):
            return jsonify(error="Cada línea debe indicar el artículo."), 400
        cantidad = linea.get("cantidad")
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad < 1:
            return jsonify(error="Cada línea debe tener una cantidad entera mayor que cero."), 400
        linea["estado_servicio"] = str(linea.get("estado_servicio") or "Entregado").strip()
        if linea["estado_servicio"] not in ESTADOS_SERVICIO:
            return jsonify(error="El estado del servicio debe ser: " + ", ".join(ESTADOS_SERVICIO) + "."), 400
    ids = [linea["id"] for linea in lineas]
    if len(set(ids)) != len(ids):
        return jsonify(error="Un mismo artículo no puede aparecer dos veces en la remisión."), 400

    articulos = {a.id: a for a in ArticuloInventario.query.filter(ArticuloInventario.id.in_(ids))}
    if len(articulos) != len(ids):
        return jsonify(error="Alguno de los artículos ya no existe. Recarga la página."), 404

    sin_stock = descontar_stock([(linea["id"], linea["cantidad"]) for linea in lineas])
    if sin_stock is not None:
        return jsonify(
            error=f"No hay suficientes unidades de {sin_stock.codigo} · {sin_stock.nombre} "
                  f"(disponibles: {sin_stock.stock}). No se descontó nada.",
            id_articulo=sin_stock.id,
        ), 409

    ultimo = db.session.query(db.func.max(Remision.consecutivo)).scalar() or 0
    remision = Remision(
        consecutivo=ultimo + 1,
        fecha=fecha,
        cliente_nombre=campos["cliente_nombre"],
        cliente_nit=campos["cliente_nit"],
        contacto=campos["contacto"] or None,
        telefono=campos["telefono"] or None,
        email=campos["email"] or None,
        tipo_servicio=tipo_servicio or None,
        documento_entrega=campos["documento_entrega"] or None,
        observaciones=campos["observaciones"] or None,
        empleado=usuario.nombre_completo or usuario.usuario,
        usuario=usuario.usuario,
        **sizfra,
    )
    db.session.add(remision)
    for linea in lineas:
        articulo = articulos[linea["id"]]
        remision.lineas.append(RemisionLinea(
            codigo=articulo.codigo,
            descripcion=articulo.nombre,
            unidad=articulo.unidad,
            procedencia=articulo.procedencia,
            estado=articulo.estado,
            subpartida=articulo.subpartida,
            valor_fob_usd=articulo.valor_fob_usd,
            cantidad=linea["cantidad"],
            estado_servicio=linea["estado_servicio"],
        ))
        articulo.estado_servicio = linea["estado_servicio"]
        if not articulo.cliente:
            articulo.cliente = remision.cliente_nombre
        db.session.add(MovimientoInventario(
            empleado=remision.empleado,
            usuario=usuario.usuario,
            articulo=articulo.nombre,
            codigo_articulo=articulo.codigo,
            categoria=articulo.categoria,
            tipo="Retiro",
            cantidad=linea["cantidad"],
            unidad=articulo.unidad,
            origen=ORIGEN_REMISION,
            observaciones=f"Remisión {remision.numero} · {remision.cliente_nombre}",
            remision=remision,
            **sizfra,
        ))
    try:
        db.session.commit()
    except IntegrityError:
        # Otra persona tomó el mismo consecutivo al mismo tiempo.
        db.session.rollback()
        return jsonify(error="Otra remisión se guardó al mismo tiempo. Inténtalo de nuevo."), 409

    return jsonify(
        remision=remision.to_dict(),
        url=url_for("remisiones.ver_remision", id_remision=remision.id),
    ), 201


@remisiones_bp.get("/api/remisiones")
def listar_remisiones():
    usuario = usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    consulta = Remision.query
    for parametro, comparar in (("desde", Remision.fecha.__ge__), ("hasta", Remision.fecha.__le__)):
        texto = (request.args.get(parametro) or "").strip()
        if texto:
            try:
                consulta = consulta.filter(comparar(date.fromisoformat(texto)))
            except ValueError:
                return jsonify(error=f"La fecha '{parametro}' debe tener el formato AAAA-MM-DD."), 400
    cliente = (request.args.get("cliente") or "").strip()
    if cliente:
        consulta = consulta.filter(
            Remision.cliente_nombre.ilike(f"%{cliente}%") | Remision.cliente_nit.ilike(f"%{cliente}%")
        )
    remisiones = consulta.order_by(Remision.consecutivo.desc()).all()
    return jsonify(
        total=len(remisiones),
        remisiones=[
            {**r.to_dict(), "url": url_for("remisiones.ver_remision", id_remision=r.id)}
            for r in remisiones
        ],
    )


@remisiones_bp.get("/remisiones/<int:id_remision>")
def ver_remision(id_remision: int):
    """Página de la remisión lista para imprimir o guardar como PDF."""
    if usuario_actual() is None:
        return redirect(url_for("main.login"))
    remision = db.session.get(Remision, id_remision)
    if remision is None:
        return render_template("remision.html", remision=None, empresa=EMPRESA), 404
    return render_template("remision.html", remision=remision, empresa=EMPRESA)
