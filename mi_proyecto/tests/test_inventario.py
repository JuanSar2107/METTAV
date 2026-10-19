"""Tests del inventario (/api/inventario/*)."""

from io import BytesIO

import pytest

from mi_app.extensions import db
from mi_app.models import ArticuloInventario


@pytest.fixture()
def crear_articulo(app):
    """Helper que crea artículos directamente en la BD de pruebas."""

    def _crear(codigo="HER-999", nombre="Taladro", stock=10, **campos):
        with app.app_context():
            articulo = ArticuloInventario(
                codigo=codigo,
                nombre=nombre,
                categoria=campos.get("categoria", "General"),
                descripcion=campos.get("descripcion", "Descripción de prueba."),
                stock=stock,
                unidad=campos.get("unidad", "unidades"),
                ubicacion=campos.get("ubicacion", "Estante Z"),
                imagen_url=campos.get("imagen_url", "https://ejemplo.com/imagen.png"),
            )
            db.session.add(articulo)
            db.session.commit()
            return articulo.id

    return _crear


def _archivo(imagen_png, nombre="imagen.png"):
    return (BytesIO(imagen_png), nombre)


def test_crear_articulo_sin_sesion_401(client, imagen_png):
    respuesta = client.post(
        "/api/inventario/",
        data={
            "nombre": "Martillo",
            "descripcion": "Martillo de uña.",
            "stock": "5",
            "imagen": _archivo(imagen_png),
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 401


def test_crear_articulo_usuario_normal_403(client, creador_usuarios, iniciar_sesion, imagen_png):
    creador_usuarios("normal")
    iniciar_sesion("normal")
    respuesta = client.post(
        "/api/inventario/",
        data={
            "nombre": "Martillo",
            "descripcion": "Martillo de uña.",
            "stock": "5",
            "imagen": _archivo(imagen_png),
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 403


def test_crear_articulo_admin(client, app, creador_usuarios, iniciar_sesion, imagen_png):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")
    respuesta = client.post(
        "/api/inventario/",
        data={
            "nombre": "Martillo",
            "categoria": "Herramientas manuales",
            "descripcion": "Martillo de uña con mango de caucho.",
            "stock": "5",
            "unidad": "unidades",
            "ubicacion": "Estante A1",
            "imagen": _archivo(imagen_png),
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 201
    articulo = respuesta.get_json()["articulo"]
    assert articulo["nombre"] == "Martillo"
    assert articulo["id"] > 0

    with app.app_context():
        guardado = db.session.get(ArticuloInventario, articulo["id"])
        assert guardado is not None
        assert guardado.stock == 5


def test_crear_articulo_imagen_invalida_400(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")
    respuesta = client.post(
        "/api/inventario/",
        data={
            "nombre": "Martillo",
            "descripcion": "Martillo.",
            "stock": "1",
            "imagen": (BytesIO(b"no soy una imagen"), "falso.png"),
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 400


def test_crear_articulo_sin_imagen_400(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")
    respuesta = client.post(
        "/api/inventario/",
        data={"nombre": "Martillo", "descripcion": "Martillo.", "stock": "1"},
    )
    assert respuesta.status_code == 400


def test_crear_articulo_stock_invalido_400(client, creador_usuarios, iniciar_sesion, imagen_png):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")
    respuesta = client.post(
        "/api/inventario/",
        data={
            "nombre": "Martillo",
            "descripcion": "Martillo.",
            "stock": "no-es-numero",
            "imagen": _archivo(imagen_png),
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 400


def test_retirar_articulo(client, crear_articulo, creador_usuarios, iniciar_sesion):
    id_articulo = crear_articulo(codigo="ART-1", stock=10)
    creador_usuarios("ana")
    iniciar_sesion("ana")

    respuesta = client.post(f"/api/inventario/{id_articulo}/retirar", json={"cantidad": 3})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["articulo"]["stock"] == 7


def test_retirar_sin_sesion_401(client, crear_articulo):
    id_articulo = crear_articulo(codigo="ART-2", stock=10)
    respuesta = client.post(f"/api/inventario/{id_articulo}/retirar", json={"cantidad": 1})
    assert respuesta.status_code == 401


def test_retirar_cantidad_invalida_400(client, crear_articulo, creador_usuarios, iniciar_sesion):
    id_articulo = crear_articulo(codigo="ART-3", stock=10)
    creador_usuarios("ana")
    iniciar_sesion("ana")

    assert client.post(f"/api/inventario/{id_articulo}/retirar", json={"cantidad": 0}).status_code == 400
    assert client.post(f"/api/inventario/{id_articulo}/retirar", json={"cantidad": "2"}).status_code == 400
    assert client.post(f"/api/inventario/{id_articulo}/retirar", json={}).status_code == 400


def test_retirar_sin_stock_suficiente_409(client, crear_articulo, creador_usuarios, iniciar_sesion):
    id_articulo = crear_articulo(codigo="ART-4", stock=2)
    creador_usuarios("ana")
    iniciar_sesion("ana")

    respuesta = client.post(f"/api/inventario/{id_articulo}/retirar", json={"cantidad": 5})
    assert respuesta.status_code == 409
    assert respuesta.get_json()["stock"] == 2


def test_retirar_articulo_inexistente_404(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.post("/api/inventario/999999/retirar", json={"cantidad": 1})
    assert respuesta.status_code == 404


def test_eliminar_articulo(client, crear_articulo, creador_usuarios, iniciar_sesion):
    id_articulo = crear_articulo(codigo="ART-5")
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")

    respuesta = client.delete(f"/api/inventario/{id_articulo}")
    assert respuesta.status_code == 200

    segunda = client.delete(f"/api/inventario/{id_articulo}")
    assert segunda.status_code == 404


def test_eliminar_articulo_solo_admin(client, crear_articulo, creador_usuarios, iniciar_sesion):
    id_articulo = crear_articulo(codigo="ART-6")
    creador_usuarios("normal")
    iniciar_sesion("normal")

    respuesta = client.delete(f"/api/inventario/{id_articulo}")
    assert respuesta.status_code == 403