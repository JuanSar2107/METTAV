from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError

from mi_app.extensions import db
from mi_app.security import usuario_actual
from mi_app.image_uploads import eliminar_imagen_subida, guardar_imagen
from mi_app.models import ArticuloInventario, Categoria, MovimientoInventario, Usuario

inventario_bp = Blueprint("inventario", __name__, url_prefix="/api/inventario")



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

    try:
        imagen_url, ruta_imagen = guardar_imagen(request.files.get("imagen"), "inventory")
    except ValueError as error:
        return jsonify(error=str(error)), 400

    articulo = ArticuloInventario(
        codigo=f"ADM-{uuid4().hex[:10].upper()}",
        nombre=nombre,
        categoria=categoria,
        descripcion=descripcion,
        stock=stock,
        stock_maximo=stock,
        unidad=unidad,
        ubicacion=ubicacion,
        imagen_url=imagen_url,
    )
    db.session.add(articulo)
    usuario = _usuario_actual()
    if stock > 0 and usuario is not None:
        db.session.add(MovimientoInventario(
            empleado=usuario.nombre_completo or usuario.usuario,
            usuario=usuario.usuario,
            articulo=nombre,
            codigo_articulo=articulo.codigo,
            categoria=categoria,
            tipo="Ingreso",
            cantidad=stock,
            unidad=unidad,
        ))
    if not Categoria.query.filter(db.func.lower(Categoria.nombre) == categoria.lower()).first():
        db.session.add(Categoria(nombre=categoria))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        ruta_imagen.unlink(missing_ok=True)
        return jsonify(error="No se pudo guardar el artículo. Inténtalo de nuevo."), 409

    return jsonify(articulo={"id": articulo.id, "nombre": articulo.nombre}), 201


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
    db.session.delete(articulo)
    db.session.commit()
    eliminar_imagen_subida(imagen_url, "inventory")
    return jsonify(mensaje="Artículo eliminado.")


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
    return jsonify(
        total=len(movimientos),
        categorias=sorted({movimiento.categoria for movimiento in movimientos if movimiento.categoria}),
        movimientos=[movimiento.to_dict() for movimiento in movimientos],
    )


@inventario_bp.post("/<int:id_articulo>/retirar")
def retirar_articulo(id_articulo: int):
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401

    datos = request.get_json(silent=True)
    cantidad = datos.get("cantidad") if isinstance(datos, dict) else None
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad < 1:
        return jsonify(error="Indica una cantidad entera mayor que cero."), 400

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
    cantidad = datos.get("cantidad") if isinstance(datos, dict) else None
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad < 1:
        return jsonify(error="Indica una cantidad entera mayor que cero."), 400

    articulo = db.session.get(ArticuloInventario, id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404

    resultado = db.session.execute(
        update(ArticuloInventario)
        .where(
            ArticuloInventario.id == id_articulo,
            (ArticuloInventario.stock_maximo == 0)
            | (ArticuloInventario.stock + cantidad <= ArticuloInventario.stock_maximo),
        )
        .values(
            stock=ArticuloInventario.stock + cantidad,
            stock_maximo=case(
                (ArticuloInventario.stock_maximo == 0, ArticuloInventario.stock + cantidad),
                else_=ArticuloInventario.stock_maximo,
            ),
        )
    )
    if resultado.rowcount == 0:
        db.session.rollback()
        articulo = db.session.get(ArticuloInventario, id_articulo)
        if articulo is None:
            return jsonify(error="El artículo no existe."), 404
        return jsonify(
            error="El ingreso supera el límite de stock del artículo.",
            stock=articulo.stock,
            stock_maximo=articulo.stock_maximo,
            disponible=max(0, articulo.stock_maximo - articulo.stock),
        ), 409

    movimiento = MovimientoInventario(
        empleado=usuario.nombre_completo or usuario.usuario,
        usuario=usuario.usuario,
        articulo=articulo.nombre,
        codigo_articulo=articulo.codigo,
        categoria=articulo.categoria,
        tipo="Ingreso",
        cantidad=cantidad,
        unidad=articulo.unidad,
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