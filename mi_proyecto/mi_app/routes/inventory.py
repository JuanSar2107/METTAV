import re
import unicodedata
from collections import Counter
from uuid import uuid4

from flask import Blueprint, jsonify, request, url_for
from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError

from mi_app.exportar import respuesta_excel, respuesta_pdf
from mi_app.routes.reports import hora_colombia
from mi_app.extensions import db
from mi_app.security import usuario_actual
from mi_app.image_uploads import eliminar_imagen_subida, guardar_imagen
from mi_app.models import (
    ArticuloInventario,
    Categoria,
    MovimientoInventario,
    RegistroAuditoria,
    SalidaIntegrada,
    Usuario,
)
from mi_app.models.inventory import (
    ESTADOS_SERVICIO,
    ORIGEN_ALTA,
    ORIGEN_IMPORTACION,
    ORIGEN_MANUAL,
    ORIGEN_SALIDA_INTEGRADA,
    PROCESOS_INTEGRACION,
    TIPOS_SERVICIO,
)
from mi_app.zona_franca import (
    campos_trazabilidad,
    campos_zona_franca,
    codigo_valido,
    leer_excel,
    normalizar_codigo,
)

inventario_bp = Blueprint("inventario", __name__, url_prefix="/api/inventario")

_RE_OPERACION = re.compile(r"^\d{1,6}$")
_RE_FORMULARIO = re.compile(r"^[A-Za-z0-9-]{1,24}$")


def datos_sizfra(datos) -> dict:
    """Valida la operación y el formulario de Sizfra (ambos opcionales)."""
    operacion = str(datos.get("operacion_sizfra") or "").strip()
    formulario = str(datos.get("formulario") or "").strip().upper()
    if operacion and not _RE_OPERACION.match(operacion):
        raise ValueError("La operación de Sizfra debe ser un número, por ejemplo 420.")
    if formulario and not _RE_FORMULARIO.match(formulario):
        raise ValueError("El formulario de Sizfra solo admite letras, números y guiones (máximo 24).")
    return {"operacion_sizfra": operacion or None, "formulario": formulario or None}


def _cantidad_valida(cantidad) -> bool:
    return not isinstance(cantidad, bool) and isinstance(cantidad, int) and cantidad >= 1


def _sin_tildes(texto: str) -> str:
    """Igual que la búsqueda del navegador: minúsculas y sin tildes."""
    return unicodedata.normalize("NFD", texto.strip().lower()).encode("ascii", "ignore").decode()


def _observaciones(datos) -> str | None:
    texto = str(datos.get("observaciones") or "").strip()
    if len(texto) > 2000:
        raise ValueError("Las observaciones no pueden superar 2000 caracteres.")
    return texto or None


def campos_servicio(datos) -> dict:
    """Cliente, tipo y estado del servicio (opcionales; para mercancía de clientes)."""
    cliente = str(datos.get("cliente") or "").strip()
    tipo = str(datos.get("tipo_servicio") or "").strip()
    estado = str(datos.get("estado_servicio") or "").strip()
    if len(cliente) > 160:
        raise ValueError("El cliente no puede superar 160 caracteres.")
    if tipo and tipo not in TIPOS_SERVICIO:
        raise ValueError("El tipo de servicio debe ser: " + ", ".join(TIPOS_SERVICIO) + ".")
    if estado and estado not in ESTADOS_SERVICIO:
        raise ValueError("El estado del servicio debe ser: " + ", ".join(ESTADOS_SERVICIO) + ".")
    return {"cliente": cliente or None, "tipo_servicio": tipo or None, "estado_servicio": estado or None}


def descontar_stock(lineas: list[tuple[int, int]]) -> ArticuloInventario | None:
    """Descuenta (id_articulo, cantidad) de cada línea en la transacción actual.

    Usa la misma condición que un retiro normal. Si a una línea le falta
    stock deshace todo y devuelve ese artículo; si todo sale bien devuelve
    None y el llamador hace el commit.
    """
    for id_articulo, cantidad in lineas:
        resultado = db.session.execute(
            update(ArticuloInventario)
            .where(
                ArticuloInventario.id == id_articulo,
                ArticuloInventario.stock >= cantidad,
                ArticuloInventario.stock_maximo >= cantidad,
            )
            .values(stock=ArticuloInventario.stock - cantidad)
        )
        if resultado.rowcount == 0:
            db.session.rollback()
            return db.session.get(ArticuloInventario, id_articulo)
    return None


def _auditar(usuario: Usuario, accion: str, codigo: str | None = None, detalle: str | None = None) -> None:
    """Agrega a la sesión un registro de auditoría (se guarda con el commit)."""
    db.session.add(RegistroAuditoria(
        accion=accion,
        codigo_articulo=codigo,
        detalle=detalle,
        empleado=usuario.nombre_completo or usuario.usuario,
        usuario=usuario.usuario,
    ))



def _usuario_actual() -> Usuario | None:
    return usuario_actual()


def _error_admin():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario.es_admin:
        return jsonify(error="Solo un administrador puede gestionar los artículos."), 403
    return None


@inventario_bp.post("/")
def crear_articulo():
    error = _error_admin()
    if error is not None:
        return error

    nombre = request.form.get("nombre", "").strip()
    categoria = request.form.get("categoria", "").strip() or "General"
    descripcion = request.form.get("descripcion", "").strip()
    stock_texto = request.form.get("stock", "").strip()
    unidad = request.form.get("unidad", "").strip() or "unidades"
    ubicacion = request.form.get("ubicacion", "").strip() or "Sin asignar"

    if not nombre or len(nombre) > 120:
        return jsonify(error="El nombre es obligatorio y no puede superar 120 caracteres."), 400
    if len(categoria) > 60 or len(unidad) > 24 or len(ubicacion) > 80:
        return jsonify(error="La categoría, unidad o ubicación supera el largo permitido."), 400
    if not descripcion or len(descripcion) > 4000:
        return jsonify(error="La descripción es obligatoria y no puede superar 4000 caracteres."), 400
    try:
        stock = int(stock_texto)
    except ValueError:
        return jsonify(error="El stock debe ser un número entero igual o mayor que cero."), 400
    if stock < 0:
        return jsonify(error="El stock no puede ser negativo."), 400

    # El código ZF es opcional: si no se indica, se genera uno interno.
    codigo = normalizar_codigo(request.form.get("codigo", ""))
    if codigo and not codigo_valido(codigo):
        return jsonify(error="El código ZF solo admite letras, números y guiones (máximo 24)."), 400
    if codigo and ArticuloInventario.query.filter_by(codigo=codigo).first() is not None:
        return jsonify(error=f"Ya existe un artículo con el código {codigo}."), 409
    try:
        campos_zf = campos_zona_franca(request.form)
        campos_zf.update(campos_trazabilidad(request.form))
        campos_zf.update(campos_servicio(request.form))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    # La imagen es opcional: sin ella se usa la misma imagen por defecto que en la importación.
    imagen = request.files.get("imagen")
    ruta_imagen = None
    if imagen is not None and imagen.filename:
        try:
            imagen_url, ruta_imagen = guardar_imagen(imagen, "inventory")
        except ValueError as error:
            return jsonify(error=str(error)), 400
    else:
        imagen_url = url_for("static", filename="images/workshop-bg.jpg")

    articulo = ArticuloInventario(
        codigo=codigo or f"ADM-{uuid4().hex[:10].upper()}",
        nombre=nombre,
        categoria=categoria,
        descripcion=descripcion,
        stock=stock,
        stock_maximo=stock,
        unidad=unidad,
        ubicacion=ubicacion,
        imagen_url=imagen_url,
        **campos_zf,
    )
    db.session.add(articulo)
    usuario = _usuario_actual()
    _auditar(usuario, "Crear artículo", articulo.codigo, f"{nombre} · stock inicial {stock} {unidad}")
    if stock > 0:
        db.session.add(MovimientoInventario(
            empleado=usuario.nombre_completo or usuario.usuario,
            usuario=usuario.usuario,
            articulo=nombre,
            codigo_articulo=articulo.codigo,
            categoria=categoria,
            tipo="Ingreso",
            cantidad=stock,
            unidad=unidad,
            origen=ORIGEN_ALTA,
        ))
    if not Categoria.query.filter(db.func.lower(Categoria.nombre) == categoria.lower()).first():
        db.session.add(Categoria(nombre=categoria))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if ruta_imagen is not None:
            ruta_imagen.unlink(missing_ok=True)
        return jsonify(error="No se pudo guardar el artículo. Inténtalo de nuevo."), 409

    return jsonify(articulo={"id": articulo.id, "nombre": articulo.nombre}), 201


# Campos que una nueva importación actualiza en un artículo que ya existe.
# El stock no se toca: lo cambian solo los ingresos y retiros.
_CAMPOS_ACTUALIZABLES = (
    "nombre", "descripcion", "categoria", "ubicacion", "codigo_interno", "grupo", "tipo",
    "marca", "subpartida", "valor_fob_usd", "procedencia", "estado",
    "serial", "responsable", "fecha_ingreso", "documento_soporte",
    "fecha_retiro", "documento_retiro", "razon_retiro",
)


@inventario_bp.post("/importar")
def importar_excel():
    """Crea o actualiza artículos desde el Excel de inventario (por código ZF)."""
    error = _error_admin()
    if error is not None:
        return error

    archivo = request.files.get("archivo")
    if archivo is None or not archivo.filename:
        return jsonify(error="Selecciona el archivo Excel (.xlsx) del inventario."), 400
    if not archivo.filename.lower().endswith(".xlsx"):
        return jsonify(error="El archivo debe ser un Excel .xlsx."), 400
    try:
        filas, errores, avisos = leer_excel(archivo.stream)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    usuario = _usuario_actual()
    existentes = {
        articulo.codigo: articulo
        for articulo in ArticuloInventario.query.filter(
            ArticuloInventario.codigo.in_([fila["codigo"] for fila in filas])
        )
    }
    categorias = {c.nombre.lower() for c in Categoria.query.all()}
    imagen_por_defecto = url_for("static", filename="images/workshop-bg.jpg")
    creados = actualizados = 0
    # Un código ZF repetido en el archivo es ambiguo: no se importa ninguna de
    # esas filas para no asignarle el código al artículo equivocado.
    repeticiones = Counter(fila["codigo"] for fila in filas)

    for fila in filas:
        codigo = fila["codigo"]
        if repeticiones[codigo] > 1:
            errores.append({
                "fila": fila["fila"],
                "codigo": codigo,
                "error": f"Código ZF repetido en {repeticiones[codigo]} filas del archivo; no se importó.",
            })
            continue

        articulo = existentes.get(codigo)
        if articulo is not None:
            cambios = [campo for campo in _CAMPOS_ACTUALIZABLES if getattr(articulo, campo) != fila[campo]]
            for campo in cambios:
                setattr(articulo, campo, fila[campo])
            if cambios:
                _auditar(
                    usuario, "Actualizar por importación", codigo,
                    "Campos: " + ", ".join(campo.replace("_", " ") for campo in cambios),
                )
            actualizados += 1
        else:
            db.session.add(ArticuloInventario(
                codigo=codigo,
                stock=fila["stock"],
                stock_maximo=fila["stock"],
                unidad=fila["unidad"],
                imagen_url=imagen_por_defecto,
                **{campo: fila[campo] for campo in _CAMPOS_ACTUALIZABLES},
            ))
            if fila["stock"] > 0:
                db.session.add(MovimientoInventario(
                    empleado=usuario.nombre_completo or usuario.usuario,
                    usuario=usuario.usuario,
                    articulo=fila["nombre"],
                    codigo_articulo=codigo,
                    categoria=fila["categoria"],
                    tipo="Ingreso",
                    cantidad=fila["stock"],
                    unidad=fila["unidad"],
                    origen=ORIGEN_IMPORTACION,
                ))
            creados += 1

        if fila["categoria"].lower() not in categorias:
            db.session.add(Categoria(nombre=fila["categoria"]))
            categorias.add(fila["categoria"].lower())

    errores.sort(key=lambda e: e["fila"])
    _auditar(
        usuario, "Importar Excel", None,
        f"{archivo.filename}: {creados} creados, {actualizados} actualizados, {len(errores)} filas con error",
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="No se pudo guardar la importación. Inténtalo de nuevo."), 409

    return jsonify(creados=creados, actualizados=actualizados, errores=errores, avisos=avisos)


@inventario_bp.get("/categorias")
def listar_categorias():
    if _usuario_actual() is None:
        return jsonify(error="Debes iniciar sesión."), 401
    categorias = Categoria.query.order_by(Categoria.nombre.asc()).all()
    return jsonify(categorias=[c.to_dict() for c in categorias])


@inventario_bp.post("/categorias")
def crear_categoria():
    error = _error_admin()
    if error is not None:
        return error

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        datos = request.form

    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        return jsonify(error="El nombre de la categoría es obligatorio."), 400
    if len(nombre) > 60:
        return jsonify(error="El nombre de la categoría no puede superar los 60 caracteres."), 400

    existente = Categoria.query.filter(db.func.lower(Categoria.nombre) == nombre.lower()).first()
    if existente is not None:
        return jsonify(
            error=f"La categoría '{existente.nombre}' ya existe.",
            categoria=existente.to_dict(),
        ), 409

    categoria = Categoria(nombre=nombre)
    db.session.add(categoria)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="No se pudo guardar la categoría."), 409

    return jsonify(
        mensaje="Categoría creada con éxito.",
        categoria=categoria.to_dict(),
    ), 201



@inventario_bp.delete("/<int:id_articulo>")
def eliminar_articulo(id_articulo: int):
    error = _error_admin()
    if error is not None:
        return error

    articulo = db.session.get(ArticuloInventario, id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404

    imagen_url = articulo.imagen_url
    _auditar(
        _usuario_actual(), "Eliminar artículo", articulo.codigo,
        f"{articulo.nombre} · tenía {articulo.stock} {articulo.unidad} en stock",
    )
    db.session.delete(articulo)
    db.session.commit()
    eliminar_imagen_subida(imagen_url, "inventory")
    return jsonify(mensaje="Artículo eliminado.")


@inventario_bp.patch("/<int:id_articulo>/servicio")
def actualizar_servicio(id_articulo: int):
    """Cambia el cliente, el tipo o el estado del servicio de un artículo y lo audita."""
    error = _error_admin()
    if error is not None:
        return error
    articulo = db.session.get(ArticuloInventario, id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="Envía los datos del servicio en formato JSON."), 400
    try:
        nuevos = campos_servicio(datos)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    nombres = {"cliente": "cliente", "tipo_servicio": "servicio", "estado_servicio": "estado"}
    cambios = [
        f"{nombres[campo]}: {getattr(articulo, campo) or '—'} → {valor or '—'}"
        for campo, valor in nuevos.items()
        if getattr(articulo, campo) != valor
    ]
    if cambios:
        for campo, valor in nuevos.items():
            setattr(articulo, campo, valor)
        _auditar(_usuario_actual(), "Actualizar servicio", articulo.codigo, "; ".join(cambios))
        db.session.commit()
    return jsonify(articulo={"id": articulo.id, **nuevos}, cambios=len(cambios))


@inventario_bp.get("/movimientos")
def listar_movimientos():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario.es_admin:
        return jsonify(error="Solo un administrador puede ver el historial de movimientos."), 403

    movimientos = (
        MovimientoInventario.query
        .order_by(MovimientoInventario.fecha_hora.desc(), MovimientoInventario.id.desc())
        .all()
    )
    formato = (request.args.get("formato") or "").lower()
    if formato not in ("xlsx", "pdf"):
        return jsonify(
            total=len(movimientos),
            categorias=sorted({movimiento.categoria for movimiento in movimientos if movimiento.categoria}),
            movimientos=[movimiento.to_dict() for movimiento in movimientos],
        )

    # Descarga: los mismos filtros que la pestaña Historial (búsqueda, categoría y día).
    texto = _sin_tildes(request.args.get("q") or "")
    categoria = (request.args.get("categoria") or "").strip()
    dia = (request.args.get("dia") or "").strip()
    filtros = []
    if texto:
        filtros.append(f"búsqueda \"{request.args['q'].strip()}\"")
    if categoria:
        filtros.append(f"categoría {categoria}")
    if dia:
        filtros.append(f"día {dia}")

    def coincide(m: MovimientoInventario) -> bool:
        contenido = _sin_tildes(" ".join(str(v or "") for v in (
            m.tipo, m.empleado, m.usuario, m.articulo, m.codigo_articulo, m.categoria, m.operacion_sizfra,
            m.formulario, m.salida.referencia if m.salida else "", m.salida.proceso if m.salida else "",
            m.observaciones, m.origen,
        )))
        return ((not texto or texto in contenido)
                and (not categoria or m.categoria == categoria)
                and (not dia or hora_colombia(m.fecha_hora)[:10] == dia))

    movimientos = [m for m in movimientos if coincide(m)]
    encabezados = ["Fecha (hora Colombia)", "Tipo", "Código", "Artículo", "Categoría", "Cantidad", "Unidad",
                   "Operación Sizfra", "Formulario", "Origen", "Detalle", "Observaciones", "Empleado", "Usuario"]

    def detalle(m: MovimientoInventario) -> str:
        if m.salida:
            return (f"Equipo · {m.salida.proceso} #{m.id_salida}" if m.rol == "Principal"
                    else f"Integrada en {m.salida.referencia} #{m.id_salida}")
        return m.remision.numero if m.remision else ""

    filas = [[hora_colombia(m.fecha_hora), m.tipo, m.codigo_articulo, m.articulo, m.categoria, m.cantidad, m.unidad,
              m.operacion_sizfra, m.formulario, m.origen, detalle(m), m.observaciones, m.empleado, m.usuario]
             for m in movimientos]
    if formato == "xlsx":
        return respuesta_excel("Historial", encabezados, filas, "historial-movimientos")
    return respuesta_pdf(
        "Historial de movimientos",
        ["Fecha", "Tipo", "Código", "Artículo", "Cant.", "Sizfra", "Origen / detalle", "Observaciones", "Empleado"],
        [[f[0], f[1], f[2], f[3], f"{f[5]} {f[6]}",
          " · ".join(x for x in (f[7] and f"Op. {f[7]}", f[8] and f"Form. {f[8]}") if x),
          " · ".join(x for x in (f[9], f[10]) if x), f[11], f[12]] for f in filas],
        "historial-movimientos",
        anchos=[0.1, 0.06, 0.12, 0.19, 0.07, 0.11, 0.14, 0.13, 0.08],
        detalle=", ".join(filtros),
        generado_por=usuario.nombre_completo or usuario.usuario,
    )


@inventario_bp.post("/<int:id_articulo>/retirar")
def retirar_articulo(id_articulo: int):
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        datos = {}
    cantidad = datos.get("cantidad")
    if not _cantidad_valida(cantidad):
        return jsonify(error="Indica una cantidad entera mayor que cero."), 400
    try:
        sizfra = datos_sizfra(datos)
        observaciones = _observaciones(datos)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    articulo = db.session.get(ArticuloInventario, id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404

    resultado = db.session.execute(
        update(ArticuloInventario)
        .where(
            ArticuloInventario.id == id_articulo,
            ArticuloInventario.stock >= cantidad,
            ArticuloInventario.stock_maximo >= cantidad,
        )
        .values(stock=ArticuloInventario.stock - cantidad)
    )
    if resultado.rowcount == 0:
        db.session.rollback()
        articulo = db.session.get(ArticuloInventario, id_articulo)
        if articulo is None:
            return jsonify(error="El artículo no existe."), 404
        if cantidad > articulo.stock_maximo:
            return jsonify(
                error="La cantidad supera el límite original del artículo.",
                stock=articulo.stock,
                stock_maximo=articulo.stock_maximo,
            ), 409
        return jsonify(error="No hay suficientes unidades en stock.", stock=articulo.stock), 409

    movimiento = MovimientoInventario(
        empleado=usuario.nombre_completo or usuario.usuario,
        usuario=usuario.usuario,
        articulo=articulo.nombre,
        codigo_articulo=articulo.codigo,
        categoria=articulo.categoria,
        tipo="Retiro",
        cantidad=cantidad,
        unidad=articulo.unidad,
        origen=ORIGEN_MANUAL,
        observaciones=observaciones,
        **sizfra,
    )
    db.session.add(movimiento)
    db.session.commit()
    articulo = db.session.get(ArticuloInventario, id_articulo)
    return jsonify(
        articulo={
            "id": articulo.id,
            "stock": articulo.stock,
            "stock_maximo": articulo.stock_maximo,
            "unidad": articulo.unidad,
        },
        movimiento=movimiento.to_dict(),
    )


@inventario_bp.post("/<int:id_articulo>/ingresar")
def ingresar_articulo(id_articulo: int):
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        datos = {}
    cantidad = datos.get("cantidad")
    if not _cantidad_valida(cantidad):
        return jsonify(error="Indica una cantidad entera mayor que cero."), 400
    try:
        sizfra = datos_sizfra(datos)
        observaciones = _observaciones(datos)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    articulo = db.session.get(ArticuloInventario, id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404

    # Los ingresos no tienen tope (materia prima y consumibles rotan
    # constantemente); stock_maximo solo guarda el stock más alto alcanzado.
    resultado = db.session.execute(
        update(ArticuloInventario)
        .where(ArticuloInventario.id == id_articulo)
        .values(
            stock=ArticuloInventario.stock + cantidad,
            stock_maximo=case(
                (
                    ArticuloInventario.stock + cantidad > ArticuloInventario.stock_maximo,
                    ArticuloInventario.stock + cantidad,
                ),
                else_=ArticuloInventario.stock_maximo,
            ),
        )
    )
    if resultado.rowcount == 0:
        db.session.rollback()
        return jsonify(error="El artículo no existe."), 404

    movimiento = MovimientoInventario(
        empleado=usuario.nombre_completo or usuario.usuario,
        usuario=usuario.usuario,
        articulo=articulo.nombre,
        codigo_articulo=articulo.codigo,
        categoria=articulo.categoria,
        tipo="Ingreso",
        cantidad=cantidad,
        unidad=articulo.unidad,
        origen=ORIGEN_MANUAL,
        observaciones=observaciones,
        **sizfra,
    )
    db.session.add(movimiento)
    db.session.commit()
    articulo = db.session.get(ArticuloInventario, id_articulo)
    return jsonify(
        articulo={
            "id": articulo.id,
            "stock": articulo.stock,
            "stock_maximo": articulo.stock_maximo,
            "unidad": articulo.unidad,
        },
        movimiento=movimiento.to_dict(),
    )


@inventario_bp.post("/salidas-integradas")
def crear_salida_integrada():
    """Da de baja en un solo registro un equipo y las partes que se le integraron.

    Recibe JSON: {"principal": {"id", "cantidad"} | null, "componentes": [{"id", "cantidad"}, ...],
    "proceso", "referencia", "observaciones", "operacion_sizfra", "formulario"}.
    Si a alguna línea le falta stock no se descuenta nada.
    """
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="Envía los datos de la salida en formato JSON."), 400

    principal = datos.get("principal")
    componentes = datos.get("componentes")
    if principal is not None and not isinstance(principal, dict):
        return jsonify(error="El equipo principal no es válido."), 400
    if not isinstance(componentes, list) or not componentes:
        return jsonify(error="Agrega al menos una parte integrada."), 400
    if len(componentes) > 50:
        return jsonify(error="Una salida admite máximo 50 partes integradas."), 400

    lineas = ([(principal, "Principal")] if principal else []) + [(c, "Integrado") for c in componentes]
    for linea, _rol in lineas:
        if not isinstance(linea, dict) or not isinstance(linea.get("id"), int) or isinstance(linea.get("id"), bool):
            return jsonify(error="Cada línea debe indicar el artículo."), 400
        if not _cantidad_valida(linea.get("cantidad")):
            return jsonify(error="Cada línea debe tener una cantidad entera mayor que cero."), 400
    ids = [linea["id"] for linea, _rol in lineas]
    if len(set(ids)) != len(ids):
        return jsonify(error="Un mismo artículo no puede aparecer dos veces en la salida."), 400

    proceso = str(datos.get("proceso") or "").strip()
    if proceso not in PROCESOS_INTEGRACION:
        return jsonify(error="Elige el proceso: " + ", ".join(PROCESOS_INTEGRACION) + "."), 400
    observaciones = str(datos.get("observaciones") or "").strip()
    if len(observaciones) > 2000:
        return jsonify(error="Las observaciones no pueden superar 2000 caracteres."), 400
    try:
        sizfra = datos_sizfra(datos)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    articulos = {a.id: a for a in ArticuloInventario.query.filter(ArticuloInventario.id.in_(ids))}
    faltantes = [i for i in ids if i not in articulos]
    if faltantes:
        return jsonify(error="Alguno de los artículos ya no existe. Recarga la página."), 404

    referencia = str(datos.get("referencia") or "").strip()
    if not referencia and principal:
        equipo = articulos[principal["id"]]
        referencia = f"{equipo.codigo} · {equipo.nombre}"
    if not referencia:
        return jsonify(error="Indica la referencia del equipo al que se integran las partes."), 400
    referencia = referencia[:120]

    sin_stock = descontar_stock([(linea["id"], linea["cantidad"]) for linea, _rol in lineas])
    if sin_stock is not None:
        return jsonify(
            error=f"No hay suficientes unidades de {sin_stock.codigo} · {sin_stock.nombre} "
                  f"(disponibles: {sin_stock.stock}). No se descontó nada.",
            id_articulo=sin_stock.id,
            stock=sin_stock.stock,
        ), 409

    salida = SalidaIntegrada(
        proceso=proceso,
        referencia=referencia,
        observaciones=observaciones or None,
        empleado=usuario.nombre_completo or usuario.usuario,
        usuario=usuario.usuario,
        **sizfra,
    )
    db.session.add(salida)
    for linea, rol in lineas:
        articulo = articulos[linea["id"]]
        db.session.add(MovimientoInventario(
            empleado=salida.empleado,
            usuario=usuario.usuario,
            articulo=articulo.nombre,
            codigo_articulo=articulo.codigo,
            categoria=articulo.categoria,
            tipo="Retiro",
            cantidad=linea["cantidad"],
            unidad=articulo.unidad,
            rol=rol,
            salida=salida,
            origen=ORIGEN_SALIDA_INTEGRADA,
            **sizfra,
        ))
    db.session.commit()

    stocks = {
        a.id: a.stock
        for a in ArticuloInventario.query.filter(ArticuloInventario.id.in_(ids))
    }
    return jsonify(salida=salida.to_dict(), stocks=stocks), 201


@inventario_bp.get("/salidas-integradas/<int:id_salida>")
def obtener_salida_integrada(id_salida: int):
    """Devuelve una salida integrada con el equipo y todas sus partes."""
    if _usuario_actual() is None:
        return jsonify(error="Debes iniciar sesión."), 401
    salida = db.session.get(SalidaIntegrada, id_salida)
    if salida is None:
        return jsonify(error="La salida no existe."), 404
    return jsonify(salida=salida.to_dict())


@inventario_bp.get("/trazabilidad/<codigo>")
def trazabilidad_articulo(codigo: str):
    """Todo lo ocurrido con un código: movimientos de stock y acciones de auditoría.

    Se busca por código (no por id) para que funcione también con artículos
    que ya se eliminaron.
    """
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario.es_admin:
        return jsonify(error="Solo un administrador puede ver la trazabilidad."), 403

    codigo = normalizar_codigo(codigo)
    articulo = ArticuloInventario.query.filter_by(codigo=codigo).first()
    movimientos = MovimientoInventario.query.filter_by(codigo_articulo=codigo).all()
    auditoria = RegistroAuditoria.query.filter_by(codigo_articulo=codigo).all()
    if articulo is None and not movimientos and not auditoria:
        return jsonify(error="No hay registros para ese código."), 404

    eventos = [{"clase": "movimiento", **m.to_dict()} for m in movimientos]
    eventos += [{"clase": "auditoria", **r.to_dict()} for r in auditoria]
    # Más reciente primero; a igual hora, el orden en que se guardaron.
    eventos.sort(key=lambda e: (e["fecha_hora"], e["clase"] == "movimiento", e["id"]), reverse=True)

    datos_articulo = None
    if articulo is not None:
        datos_articulo = {
            "id": articulo.id,
            "codigo": articulo.codigo,
            "nombre": articulo.nombre,
            "stock": articulo.stock,
            "unidad": articulo.unidad,
            "serial": articulo.serial,
            "responsable": articulo.responsable,
            "fecha_ingreso": articulo.fecha_ingreso.isoformat() if articulo.fecha_ingreso else None,
            "documento_soporte": articulo.documento_soporte,
            "fecha_retiro": articulo.fecha_retiro.isoformat() if articulo.fecha_retiro else None,
            "documento_retiro": articulo.documento_retiro,
            "razon_retiro": articulo.razon_retiro,
            "cliente": articulo.cliente,
            "tipo_servicio": articulo.tipo_servicio,
            "estado_servicio": articulo.estado_servicio,
        }
    return jsonify(codigo=codigo, articulo=datos_articulo, eventos=eventos)