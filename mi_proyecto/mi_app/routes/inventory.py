from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, request, session
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from mi_app.extensions import db
from mi_app.models import ArticuloInventario, Usuario

inventario_bp = Blueprint("inventario", __name__, url_prefix="/api/inventario")
_FORMATOS_IMAGEN = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
_MAX_PIXELES_IMAGEN = 20_000_000


def _usuario_actual() -> Usuario | None:
    id_usuario = session.get("id_usuario")
    if not isinstance(id_usuario, int):
        return None
    return db.session.get(Usuario, id_usuario)


def _error_admin():
    usuario = _usuario_actual()
    if usuario is None:
        return jsonify(error="Debes iniciar sesión."), 401
    if not usuario.es_admin:
        return jsonify(error="Solo un administrador puede gestionar los artículos."), 403
    return None


def _guardar_imagen(archivo) -> tuple[str, Path]:
    if archivo is None or not archivo.filename:
        raise ValueError("Selecciona una imagen para el artículo.")

    try:
        with Image.open(archivo.stream) as imagen:
            formato = imagen.format
            ancho, alto = imagen.size
            if formato not in _FORMATOS_IMAGEN:
                raise ValueError("La imagen debe ser JPEG, PNG o WEBP.")
            if ancho * alto > _MAX_PIXELES_IMAGEN:
                raise ValueError("La imagen tiene dimensiones demasiado grandes.")
            imagen.verify()
        archivo.stream.seek(0)
        with Image.open(archivo.stream) as imagen:
            imagen = ImageOps.exif_transpose(imagen)
            if formato == "JPEG":
                imagen = imagen.convert("RGB")
                opciones = {"quality": 88, "optimize": True}
            elif formato == "WEBP":
                imagen = imagen.convert("RGBA" if "A" in imagen.getbands() else "RGB")
                opciones = {"quality": 88, "method": 6}
            else:
                opciones = {"optimize": True}
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("El archivo no es una imagen válida.") from error

    nombre_archivo = f"{uuid4().hex}{_FORMATOS_IMAGEN[formato]}"
    carpeta = Path(current_app.static_folder) / "images" / "inventory"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre_archivo
    imagen.save(ruta, format=formato, **opciones)
    return f"/static/images/inventory/{nombre_archivo}", ruta


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
        imagen_url, ruta_imagen = _guardar_imagen(request.files.get("imagen"))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    articulo = ArticuloInventario(
        codigo=f"ADM-{uuid4().hex[:10].upper()}",
        nombre=nombre,
        categoria=categoria,
        descripcion=descripcion,
        stock=stock,
        unidad=unidad,
        ubicacion=ubicacion,
        imagen_url=imagen_url,
    )
    db.session.add(articulo)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        ruta_imagen.unlink(missing_ok=True)
        return jsonify(error="No se pudo guardar el artículo. Inténtalo de nuevo."), 409

    return jsonify(articulo={"id": articulo.id, "nombre": articulo.nombre}), 201


@inventario_bp.delete("/<int:id_articulo>")
def eliminar_articulo(id_articulo: int):
    error = _error_admin()
    if error is not None:
        return error

    articulo = db.session.get(ArticuloInventario, id_articulo)
    if articulo is None:
        return jsonify(error="El artículo no existe."), 404

    ruta_imagen = None
    nombre_archivo = Path(urlparse(articulo.imagen_url).path).name
    if articulo.imagen_url.startswith("/static/images/inventory/") and nombre_archivo:
        ruta_imagen = Path(current_app.static_folder) / "images" / "inventory" / nombre_archivo

    db.session.delete(articulo)
    db.session.commit()
    if ruta_imagen is not None:
        ruta_imagen.unlink(missing_ok=True)
    return jsonify(mensaje="Artículo eliminado.")


@inventario_bp.post("/<int:id_articulo>/retirar")
def retirar_articulo(id_articulo: int):
    if _usuario_actual() is None:
        return jsonify(error="Debes iniciar sesión."), 401

    datos = request.get_json(silent=True)
    cantidad = datos.get("cantidad") if isinstance(datos, dict) else None
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad < 1:
        return jsonify(error="Indica una cantidad entera mayor que cero."), 400

    resultado = db.session.execute(
        update(ArticuloInventario)
        .where(ArticuloInventario.id == id_articulo, ArticuloInventario.stock >= cantidad)
        .values(stock=ArticuloInventario.stock - cantidad)
    )
    if resultado.rowcount == 0:
        db.session.rollback()
        articulo = db.session.get(ArticuloInventario, id_articulo)
        if articulo is None:
            return jsonify(error="El artículo no existe."), 404
        return jsonify(error="No hay suficientes unidades en stock.", stock=articulo.stock), 409

    db.session.commit()
    articulo = db.session.get(ArticuloInventario, id_articulo)
    return jsonify(articulo={"id": articulo.id, "stock": articulo.stock, "unidad": articulo.unidad})