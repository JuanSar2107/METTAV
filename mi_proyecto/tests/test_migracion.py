"""Tests del script migrar_a_postgres.py.

El destino es TEST_DATABASE_URL si está definida (PostgreSQL real) o, si no,
otro archivo SQLite: la lógica de copia es la misma.
"""

import os

import pytest
from sqlalchemy import create_engine

from mi_app import create_app
from mi_app.database import normalizar_url
from mi_app.extensions import db
from mi_app.models import Categoria, MovimientoInventario, Usuario
from migrar_a_postgres import migrar


@pytest.fixture()
def origen(tmp_path):
    """Base SQLite con datos, creada con la propia app."""
    ruta = tmp_path / "origen.sqlite3"
    url = f"sqlite:///{ruta.as_posix()}"
    app = create_app({"TESTING": True, "SECRET_KEY": "x", "SQLALCHEMY_DATABASE_URI": url})
    with app.app_context():
        admin = Usuario(usuario="jefe", es_admin=True)
        admin.establecer_contrasena("clave123")
        db.session.add(admin)
        db.session.add(MovimientoInventario(
            empleado="Jefe", usuario="jefe", articulo="Taladro", codigo_articulo="HER-001",
            categoria="General", tipo="Retiro", cantidad=2, unidad="unidades",
        ))
        db.session.commit()
        db.session.remove()
        db.engine.dispose()
    return url


@pytest.fixture()
def destino(tmp_path):
    url = normalizar_url(os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'destino.sqlite3').as_posix()}")
    yield url
    motor = create_engine(url)
    db.metadata.drop_all(motor)
    motor.dispose()


def _app_sobre(url):
    return create_app({"TESTING": True, "SECRET_KEY": "x", "SQLALCHEMY_DATABASE_URI": url})


def test_migrar_copia_todo_y_conserva_ids(origen, destino):
    copiadas = migrar(origen, destino)
    assert copiadas["usuarios"] == 1
    assert copiadas["movimientos_inventario"] == 1
    assert copiadas["categorias"] >= 5  # las sembradas por defecto

    app = _app_sobre(destino)
    with app.app_context():
        jefe = Usuario.query.filter_by(usuario="jefe").one()
        assert jefe.es_admin is True
        assert jefe.verificar_contrasena("clave123")
        assert MovimientoInventario.query.one().cantidad == 2
        # Los IDs nuevos continúan después de los copiados
        ultimo = db.session.query(db.func.max(Categoria.id)).scalar()
        nueva = Categoria(nombre="Nueva")
        db.session.add(nueva)
        db.session.commit()
        assert nueva.id == ultimo + 1
        db.session.remove()
        db.engine.dispose()


def test_migrar_no_pisa_un_destino_con_datos(origen, destino):
    migrar(origen, destino)
    with pytest.raises(RuntimeError, match="ya tiene datos"):
        migrar(origen, destino)
    # Con vaciar_destino sí reemplaza
    assert migrar(origen, destino, vaciar_destino=True)["usuarios"] == 1
