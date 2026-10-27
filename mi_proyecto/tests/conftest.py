"""Configuración compartida de pytest para la app METTAV.

Cada test usa una base de datos SQLite temporal y una carpeta de
imágenes temporal, de modo que nunca se tocan la BD ni los archivos
reales del proyecto.
"""

import os
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

# Permite importar `mi_app` aunque pytest se ejecute desde otra carpeta
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mi_app import create_app
from mi_app.database import normalizar_url
from mi_app.extensions import db
from mi_app.models import Usuario  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    """App Flask aislada con BD SQLite y carpeta estática temporales."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-de-prueba",
            # TEST_DATABASE_URL permite correr los tests contra PostgreSQL
            "SQLALCHEMY_DATABASE_URI": normalizar_url(os.environ["TEST_DATABASE_URL"])
            if os.environ.get("TEST_DATABASE_URL")
            else f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    # Las imágenes subidas van a una carpeta temporal, no a la del proyecto
    app.static_folder = str(tmp_path / "static")
    (tmp_path / "static" / "images" / "inventory").mkdir(parents=True, exist_ok=True)
    (tmp_path / "static" / "images" / "profiles").mkdir(parents=True, exist_ok=True)

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Cliente HTTP de Flask para probar las rutas."""
    return app.test_client()


@pytest.fixture()
def creador_usuarios(app):
    """Helper que crea usuarios directamente en la BD de pruebas."""

    def _crear(nombre, contrasena="clave123", es_admin=False, **campos):
        with app.app_context():
            usuario = Usuario(usuario=nombre, es_admin=es_admin, **campos)
            usuario.establecer_contrasena(contrasena)
            db.session.add(usuario)
            db.session.commit()
            return usuario.id_usuario

    return _crear


@pytest.fixture()
def iniciar_sesion(client):
    """Helper que inicia sesión con un usuario ya creado."""

    def _iniciar(nombre, contrasena="clave123"):
        return client.post("/api/login", json={"usuario": nombre, "contrasena": contrasena})

    return _iniciar


@pytest.fixture()
def imagen_png():
    """Devuelve los bytes de una imagen PNG pequeña y válida."""
    bufer = BytesIO()
    Image.new("RGB", (10, 10), (200, 30, 30)).save(bufer, format="PNG")
    return bufer.getvalue()