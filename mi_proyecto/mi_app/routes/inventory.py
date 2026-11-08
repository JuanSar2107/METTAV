import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, jsonify, request, send_file, url_for
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
    Remision,
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
from mi_app.documentos import guardar_documento, ruta_documento
from mi_app.zona_franca import (
    CATEGORIAS_SIGLA,
    UBICACIONES_SIGLA,
    campos_trazabilidad,
    campos_zona_franca,
    codigo_valido,
    codigos_siguientes,
    grupo_por_ubicacion,
    leer_excel,
    normalizar_codigo,
    validar_sin_salto,
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


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _articulo_activo(id_articulo: int) -> ArticuloInventario | None:
    """El artículo, si existe y no está dado de baja: sobre una baja no se opera."""
    articulo = db.session.get(ArticuloInventario, id_articulo)
    if articulo is None or articulo.dado_de_baja_en is not None:
        return None
    return articulo


def _sumar_stock(id_articulo: int, cantidad: int) -> int:
    """Suma unidades; stock_maximo guarda el stock más alto alcanzado. Devuelve filas tocadas."""
    return db.session.execute(
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
    ).rowcount


def _revertir_stock(codigo: str, tipo: str, cantidad: int) -> str | None:
    """Deshace el efecto de un movimiento en el stock; devuelve el motivo si no se puede."""
    articulo = ArticuloInventario.query.filter_by(codigo=codigo).first()
    if articulo is None:
        return f"El artículo {codigo} ya no existe; no se puede devolver su stock."
    if articulo.dado_de_baja_en is not None:
        return f"El artículo {codigo} está dado de baja. Reactívalo antes de anular."
    if tipo != "Ingreso":
        _sumar_stock(articulo.id, cantidad)
        return None
    disponibles = articulo.stock
    resultado = db.session.execute(
        update(ArticuloInventario)
        .where(ArticuloInventario.id == articulo.id, ArticuloInventario.stock >= cantidad)
        .values(stock=ArticuloInventario.stock - cantidad)
    )
    if resultado.rowcount == 0:
        return (f"No se puede anular el ingreso de {codigo}: se necesitan {cantidad} unidades "
                f"y solo quedan {disponibles}. Anula primero las salidas que las usaron.")
    return None


@inventario_bp.get("/siguiente-codigo")
def siguiente_codigo():
    """Código ZF e interno que siguen para una categoría, ubicación y tipo."""
    error = _error_admin()
    if error is not None:
        return error
    try:
        codigo, interno = codigos_siguientes(
            request.args.get("categoria", "").strip().upper(),
            request.args.get("ubicacion", "").strip().upper(),
            request.args.get("tipo", "").strip().upper(),
        )
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(codigo=codigo, codigo_interno=interno)


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

    # Con categoría, ubicación y tipo el código sale consecutivo: se calcula aquí, no se
    # confía en el del navegador. Sin ellos se admite uno escrito a mano (p. ej. SER-...)
    # y, si no se indica ninguno, se genera uno interno.
    sigla_categoria = request.form.get("sigla_categoria", "").strip().upper()
    sigla_ubicacion = request.form.get("sigla_ubicacion", "").strip().upper()
    tipo_codigo = request.form.get("tipo", "").strip().upper()
    codigo_automatico = bool(sigla_categoria or sigla_ubicacion)
    try:
        campos_zf = campos_zona_franca(request.form)
        campos_zf.update(campos_trazabilidad(request.form))
        campos_zf.update(campos_servicio(request.form))
        if codigo_automatico:
            codigo, campos_zf["codigo_interno"] = codigos_siguientes(sigla_categoria, sigla_ubicacion, tipo_codigo)
        else:
            codigo = normalizar_codigo(request.form.get("codigo", ""))
            if codigo and not codigo_valido(codigo):
                raise ValueError("El código ZF solo admite letras, números y guiones (máximo 24).")
            if codigo:
                validar_sin_salto(codigo)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    if codigo and ArticuloInventario.query.filter_by(codigo=codigo).first() is not None:
        return jsonify(error=f"Ya existe un artículo con el código {codigo}."), 409
    if codigo_automatico:
        categoria = CATEGORIAS_SIGLA[sigla_categoria]
        if ubicacion == "Sin asignar":
            ubicacion = UBICACIONES_SIGLA[sigla_ubicacion]
        campos_zf["grupo"] = campos_zf["grupo"] or grupo_por_ubicacion(sigla_ubicacion)

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


@inventario_bp.put("/<int:id_articulo>")
def actualizar_articulo(id_articulo: int):
    """Corrige los datos de un artículo y deja en la auditoría qué campos cambiaron.

    El código (es el de Sizfra y el de su historia) y el stock no se editan aquí:
    el stock cambia solo con ingresos, retiros, salidas y remisiones. El cliente y
    el servicio tienen su propio formulario.
    """
    error = _error_admin()
    if error is not None:
        return error
    articulo = _articulo_activo(id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404

    nuevos = {
        "nombre": request.form.get("nombre", "").strip(),
        "categoria": request.form.get("categoria", "").strip() or "General",
        "descripcion": request.form.get("descripcion", "").strip(),
        "unidad": request.form.get("unidad", "").strip() or "unidades",
        "ubicacion": request.form.get("ubicacion", "").strip() or "Sin asignar",
    }
    if not nuevos["nombre"] or len(nuevos["nombre"]) > 120:
        return jsonify(error="El nombre es obligatorio y no puede superar 120 caracteres."), 400
    if len(nuevos["categoria"]) > 60 or len(nuevos["unidad"]) > 24 or len(nuevos["ubicacion"]) > 80:
        return jsonify(error="La categoría, unidad o ubicación supera el largo permitido."), 400
    if not nuevos["descripcion"] or len(nuevos["descripcion"]) > 4000:
        return jsonify(error="La descripción es obligatoria y no puede superar 4000 caracteres."), 400
    try:
        nuevos.update(campos_zona_franca(request.form))
        nuevos.update(campos_trazabilidad(request.form))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    # El código interno y el tipo forman parte del código: no se editan.
    nuevos["codigo_interno"] = articulo.codigo_interno
    nuevos["tipo"] = articulo.tipo

    cambios = [campo for campo, valor in nuevos.items() if getattr(articulo, campo) != valor]

    imagen = request.files.get("imagen")
    imagen_anterior = None
    if imagen is not None and imagen.filename:
        try:
            imagen_url, _ruta = guardar_imagen(imagen, "inventory")
        except ValueError as error:
            return jsonify(error=str(error)), 400
        imagen_anterior = articulo.imagen_url
        articulo.imagen_url = imagen_url
        cambios.append("imagen")

    if cambios:
        for campo, valor in nuevos.items():
            setattr(articulo, campo, valor)
        if not Categoria.query.filter(db.func.lower(Categoria.nombre) == nuevos["categoria"].lower()).first():
            db.session.add(Categoria(nombre=nuevos["categoria"]))
        _auditar(
            _usuario_actual(), "Editar artículo", articulo.codigo,
            "Campos: " + ", ".join(campo.replace("_", " ") for campo in cambios),
        )
        db.session.commit()
    if imagen_anterior:
        eliminar_imagen_subida(imagen_anterior, "inventory")
    return jsonify(articulo={"id": articulo.id, "nombre": articulo.nombre}, cambios=len(cambios))


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
        if articulo is not None and articulo.dado_de_baja_en is not None:
            errores.append({
                "fila": fila["fila"],
                "codigo": codigo,
                "error": "Ese código está dado de baja; reactívalo en Reportes si debe volver al inventario.",
            })
            continue
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

    articulo = _articulo_activo(id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404

    # Con historial no se borra: se da de baja para conservar su trazabilidad y su código.
    if MovimientoInventario.query.filter_by(codigo_articulo=articulo.codigo).first() is not None:
        datos = request.get_json(silent=True)
        motivo = str(datos.get("motivo") or "").strip() if isinstance(datos, dict) else ""
        if len(motivo) > 500:
            return jsonify(error="El motivo no puede superar 500 caracteres."), 400
        usuario = _usuario_actual()
        articulo.dado_de_baja_en = _ahora_utc()
        articulo.dado_de_baja_por = usuario.usuario
        articulo.motivo_baja = motivo or None
        _auditar(
            usuario, "Dar de baja", articulo.codigo,
            f"{articulo.nombre} · tenía {articulo.stock} {articulo.unidad}"
            + (f" · Motivo: {motivo}" if motivo else ""),
        )
        db.session.commit()
        return jsonify(mensaje="Artículo dado de baja. Su historial se conserva.", baja=True)

    imagen_url = articulo.imagen_url
    _auditar(
        _usuario_actual(), "Eliminar artículo", articulo.codigo,
        f"{articulo.nombre} · tenía {articulo.stock} {articulo.unidad} en stock",
    )
    db.session.delete(articulo)
    db.session.commit()
    eliminar_imagen_subida(imagen_url, "inventory")
    return jsonify(mensaje="Artículo eliminado.", baja=False)


@inventario_bp.post("/<int:id_articulo>/reactivar")
def reactivar_articulo(id_articulo: int):
    """Devuelve al inventario un artículo dado de baja, con el stock que tenía."""
    error = _error_admin()
    if error is not None:
        return error
    articulo = db.session.get(ArticuloInventario, id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404
    if articulo.dado_de_baja_en is None:
        return jsonify(error="El artículo no está dado de baja."), 409
    articulo.dado_de_baja_en = articulo.dado_de_baja_por = articulo.motivo_baja = None
    _auditar(_usuario_actual(), "Reactivar artículo", articulo.codigo, articulo.nombre)
    db.session.commit()
    return jsonify(mensaje="Artículo reactivado.")


@inventario_bp.patch("/<int:id_articulo>/servicio")
def actualizar_servicio(id_articulo: int):
    """Cambia el cliente, el tipo o el estado del servicio de un artículo y lo audita."""
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario.puede_operar:
        return jsonify(error="No tienes permiso para cambiar el servicio."), 403
    articulo = _articulo_activo(id_articulo)
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
    if not usuario.puede_operar:
        return jsonify(error="No tienes permiso para ver el historial de movimientos."), 403

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
                   "Operación Sizfra", "Formulario", "Origen", "Detalle", "Observaciones", "Empleado", "Usuario",
                   "Documento soporte", "Estado", "Motivo de anulación"]

    def detalle(m: MovimientoInventario) -> str:
        if m.salida:
            return (f"Equipo · {m.salida.proceso} #{m.id_salida}" if m.rol == "Principal"
                    else f"Integrada en {m.salida.referencia} #{m.id_salida}")
        return m.remision.numero if m.remision else ""

    filas = [[hora_colombia(m.fecha_hora), m.tipo, m.codigo_articulo, m.articulo, m.categoria, m.cantidad, m.unidad,
              m.operacion_sizfra, m.formulario, m.origen, detalle(m), m.observaciones, m.empleado, m.usuario,
              m.documento_nombre, "Anulado" if m.anulado_en else "Vigente", m.motivo_anulacion]
             for m in movimientos]
    if formato == "xlsx":
        return respuesta_excel("Historial", encabezados, filas, "historial-movimientos")
    return respuesta_pdf(
        "Historial de movimientos",
        ["Fecha", "Tipo", "Código", "Artículo", "Cant.", "Sizfra", "Origen / detalle", "Observaciones", "Empleado"],
        [[f[0], f"{f[1]} (ANULADO)" if f[15] == "Anulado" else f[1], f[2], f[3], f"{f[5]} {f[6]}",
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

    articulo = _articulo_activo(id_articulo)
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
        # "Ingresar existencias" llega como formulario porque puede traer el documento soporte.
        datos = request.form
    cantidad = datos.get("cantidad")
    if isinstance(cantidad, str) and cantidad.strip().isdigit():
        cantidad = int(cantidad)
    if not _cantidad_valida(cantidad):
        return jsonify(error="Indica una cantidad entera mayor que cero."), 400
    try:
        sizfra = datos_sizfra(datos)
        observaciones = _observaciones(datos)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    articulo = _articulo_activo(id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404

    documento = request.files.get("documento")
    documento_archivo = documento_nombre = None
    if documento is not None and documento.filename:
        try:
            documento_archivo, documento_nombre, _ruta = guardar_documento(documento)
        except ValueError as error:
            return jsonify(error=str(error)), 400

    # Los ingresos no tienen tope (materia prima y consumibles rotan constantemente).
    if _sumar_stock(id_articulo, cantidad) == 0:
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
        documento_archivo=documento_archivo,
        documento_nombre=documento_nombre,
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


@inventario_bp.get("/movimientos/<int:id_movimiento>/documento")
def descargar_documento(id_movimiento: int):
    """Descarga el documento soporte de un ingreso."""
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario.puede_operar:
        return jsonify(error="No tienes permiso para ver los documentos soporte."), 403
    movimiento = db.session.get(MovimientoInventario, id_movimiento)
    if movimiento is None or not movimiento.documento_archivo:
        return jsonify(error="El movimiento no tiene documento soporte."), 404
    ruta, tipo = ruta_documento(movimiento.documento_archivo)
    if not ruta.is_file():
        return jsonify(error="No se encontró el archivo del documento soporte."), 404
    return send_file(ruta, mimetype=tipo, as_attachment=True, download_name=movimiento.documento_nombre)


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

    articulos = {
        a.id: a
        for a in ArticuloInventario.query.filter(
            ArticuloInventario.id.in_(ids), ArticuloInventario.dado_de_baja_en.is_(None)
        )
    }
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
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    salida = db.session.get(SalidaIntegrada, id_salida)
    # A quien no opera el inventario se le responde igual que si no existiera.
    if salida is None or not (usuario.puede_operar or salida.usuario == usuario.usuario):
        return jsonify(error="La salida no existe."), 404
    return jsonify(salida=salida.to_dict())


@inventario_bp.post("/movimientos/<int:id_movimiento>/anular")
def anular_movimiento(id_movimiento: int):
    """Corrige un error sin borrar: marca el registro como anulado y devuelve el stock.

    Una salida integrada o una remisión se anulan completas, porque fueron una
    sola operación. Si alguna línea no se puede revertir no cambia nada.
    """
    error = _error_admin()
    if error is not None:
        return error
    datos = request.get_json(silent=True)
    motivo = str(datos.get("motivo") or "").strip() if isinstance(datos, dict) else ""
    if not motivo:
        return jsonify(error="Indica el motivo de la anulación."), 400
    if len(motivo) > 500:
        return jsonify(error="El motivo no puede superar 500 caracteres."), 400

    movimiento = db.session.get(MovimientoInventario, id_movimiento)
    if movimiento is None:
        return jsonify(error="El movimiento no existe."), 404
    if movimiento.anulado_en is not None:
        return jsonify(error="Este movimiento ya está anulado."), 409

    registro = movimiento.salida or movimiento.remision
    if movimiento.id_salida:
        grupo = MovimientoInventario.query.filter_by(id_salida=movimiento.id_salida).all()
        referencia = f"Salida integrada #{movimiento.id_salida}"
    elif movimiento.id_remision:
        grupo = MovimientoInventario.query.filter_by(id_remision=movimiento.id_remision).all()
        referencia = f"Remisión {movimiento.remision.numero}"
    else:
        grupo = [movimiento]
        referencia = "Movimiento individual"
    lineas = [(m.id, m.codigo_articulo, m.tipo, m.cantidad, m.unidad) for m in grupo]

    usuario = _usuario_actual()
    marcas = {"anulado_en": _ahora_utc(), "anulado_por": usuario.usuario, "motivo_anulacion": motivo}
    ids = [linea[0] for linea in lineas]
    # La condición impide que dos anulaciones simultáneas devuelvan el stock dos veces.
    marcados = db.session.execute(
        update(MovimientoInventario)
        .where(MovimientoInventario.id.in_(ids), MovimientoInventario.anulado_en.is_(None))
        .values(**marcas)
    ).rowcount
    if marcados != len(ids):
        db.session.rollback()
        return jsonify(error="Este movimiento ya está anulado."), 409

    for _id, codigo, tipo, cantidad, _unidad in lineas:
        problema = _revertir_stock(codigo, tipo, cantidad)
        if problema is not None:
            db.session.rollback()
            return jsonify(error=problema), 409

    if registro is not None:
        for campo, valor in marcas.items():
            setattr(registro, campo, valor)
    if isinstance(registro, Remision):
        for linea in registro.lineas:
            articulo = ArticuloInventario.query.filter_by(codigo=linea.codigo).first()
            # Solo si nadie cambió el estado después de la remisión.
            if articulo is not None and articulo.estado_servicio == linea.estado_servicio:
                articulo.estado_servicio = linea.estado_servicio_anterior
    for _id, codigo, tipo, cantidad, unidad in lineas:
        _auditar(usuario, "Anular movimiento", codigo, f"{tipo} de {cantidad} {unidad} · {referencia} · Motivo: {motivo}")
    db.session.commit()
    return jsonify(mensaje="Anulación registrada.", anulados=len(ids))


@inventario_bp.get("/trazabilidad/<codigo>")
def trazabilidad_articulo(codigo: str):
    """Todo lo ocurrido con un código: movimientos de stock y acciones de auditoría.

    Se busca por código (no por id) para que funcione también con artículos
    que ya se eliminaron.
    """
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario.puede_operar:
        return jsonify(error="No tienes permiso para ver la trazabilidad."), 403

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
            "dado_de_baja": articulo.dado_de_baja_en is not None,
            "motivo_baja": articulo.motivo_baja,
        }
    return jsonify(codigo=codigo, articulo=datos_articulo, eventos=eventos)