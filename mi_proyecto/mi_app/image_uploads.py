from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

_FORMATOS_IMAGEN = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
_CARPETAS_PERMITIDAS = {"inventory", "profiles"}
_MAX_PIXELES_IMAGEN = 20_000_000


def guardar_imagen(archivo: FileStorage | None, carpeta_nombre: str) -> tuple[str, Path]:
    if carpeta_nombre not in _CARPETAS_PERMITIDAS:
        raise ValueError("La carpeta de imágenes no está permitida.")
    if archivo is None or not archivo.filename:
        raise ValueError("Selecciona una imagen.")

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
    ruta = Path(current_app.static_folder) / "images" / carpeta_nombre / nombre_archivo
    ruta.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(ruta, format=formato, **opciones)
    return f"/static/images/{carpeta_nombre}/{nombre_archivo}", ruta


def eliminar_imagen_subida(url_imagen: str | None, carpeta_nombre: str) -> None:
    if carpeta_nombre not in _CARPETAS_PERMITIDAS or not url_imagen:
        return
    prefijo = f"/static/images/{carpeta_nombre}/"
    ruta_url = urlparse(url_imagen).path
    if not ruta_url.startswith(prefijo):
        return
    nombre_archivo = Path(ruta_url).name
    if nombre_archivo:
        ruta = Path(current_app.static_folder) / "images" / carpeta_nombre / nombre_archivo
        ruta.unlink(missing_ok=True)