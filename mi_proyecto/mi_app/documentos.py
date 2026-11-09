"""Documentos soporte de los ingresos (factura, remisión, formulario...).

Se guardan fuera de /static porque son privados: solo se descargan con sesión,
por la ruta del movimiento.
"""

from pathlib import Path
from uuid import uuid4

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

from mi_app.validacion import ErrorValidacion

_FORMATOS_IMAGEN = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
_MIME = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _extension(archivo: FileStorage) -> str:
    """Decide el tipo por el contenido, no por el nombre que trae el archivo."""
    inicio = archivo.stream.read(5)
    archivo.stream.seek(0)
    if inicio == b"%PDF-":
        return ".pdf"
    try:
        with Image.open(archivo.stream) as imagen:
            formato = imagen.format
            imagen.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        formato = None
    archivo.stream.seek(0)
    if formato not in _FORMATOS_IMAGEN:
        raise ErrorValidacion("El documento soporte debe ser un PDF o una imagen (JPG, PNG o WEBP).")
    return _FORMATOS_IMAGEN[formato]


def guardar_documento(archivo: FileStorage) -> tuple[str, str, Path]:
    """Devuelve (nombre en disco, nombre original, ruta)."""
    extension = _extension(archivo)
    carpeta = Path(current_app.config["DOCUMENTOS_FOLDER"])
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid4().hex}{extension}"
    ruta = carpeta / nombre
    archivo.save(ruta)
    original = Path((archivo.filename or "").replace("\\", "/")).name.strip()[:200]
    return nombre, original or f"documento{extension}", ruta


def ruta_documento(nombre: str) -> tuple[Path, str]:
    """Ruta en disco y tipo de un documento guardado."""
    return Path(current_app.config["DOCUMENTOS_FOLDER"]) / Path(nombre).name, _MIME[Path(nombre).suffix]
