"""Tests de validación, almacenamiento y eliminación de imágenes subidas."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from mi_app.image_uploads import eliminar_imagen_subida, guardar_imagen


def _archivo_imagen(formato="PNG", nombre=None):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (20, 90, 160)).save(buffer, format=formato)
    buffer.seek(0)
    extension = formato.lower()
    return FileStorage(
        stream=buffer,
        filename=nombre if nombre is not None else f"imagen.{extension}",
    )


@pytest.mark.parametrize(
    ("formato", "extension"),
    [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")],
)
def test_guardar_imagen_guarda_formatos_permitidos(app, formato, extension):
    with app.app_context():
        url, ruta = guardar_imagen(_archivo_imagen(formato), "profiles")

    assert ruta.is_file()
    assert ruta.suffix == extension
    assert url == f"/static/images/profiles/{ruta.name}"
    with Image.open(ruta) as imagen:
        assert imagen.size == (8, 8)


@pytest.mark.parametrize(
    ("archivo", "carpeta", "mensaje"),
    [
        (None, "profiles", "Selecciona una imagen."),
        (_archivo_imagen(nombre=""), "profiles", "Selecciona una imagen."),
        (_archivo_imagen("GIF"), "profiles", "La imagen debe ser JPEG, PNG o WEBP."),
        (FileStorage(stream=BytesIO(b"no es una imagen"), filename="falso.png"), "profiles", "El archivo no es una imagen válida."),
        (_archivo_imagen(), "otro", "La carpeta de imágenes no está permitida."),
    ],
)
def test_guardar_imagen_rechaza_entradas_invalidas(app, archivo, carpeta, mensaje):
    with app.app_context(), pytest.raises(ValueError, match=mensaje):
        guardar_imagen(archivo, carpeta)


def test_guardar_imagen_rechaza_imagen_con_demasiados_pixeles(app, monkeypatch):
    monkeypatch.setattr("mi_app.image_uploads._MAX_PIXELES_IMAGEN", 10)
    with app.app_context(), pytest.raises(ValueError, match="dimensiones demasiado grandes"):
        guardar_imagen(_archivo_imagen(), "profiles")


def test_eliminar_imagen_subida_borra_archivo_local(app):
    with app.app_context():
        url, ruta = guardar_imagen(_archivo_imagen(), "inventory")
        eliminar_imagen_subida(url, "inventory")

    assert not ruta.exists()


def test_eliminar_imagen_subida_ignora_rutas_no_confiables(app):
    archivo = Path(app.static_folder) / "images" / "profiles" / "conservar.png"
    archivo.write_bytes(b"contenido")

    with app.app_context():
        eliminar_imagen_subida("https://ejemplo.com/conservar.png", "profiles")
        eliminar_imagen_subida("/static/images/profiles/conservar.png", "otra")
        eliminar_imagen_subida(None, "profiles")

    assert archivo.read_bytes() == b"contenido"