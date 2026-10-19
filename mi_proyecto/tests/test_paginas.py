"""Tests de páginas públicas y de la documentación de rutas."""


def test_pagina_login_muestra_pantalla(client):
    respuesta = client.get("/")
    assert respuesta.status_code == 200
    assert "METTAV" in respuesta.get_data(as_text=True)


def test_dashboard_sin_sesion_redirige(client):
    respuesta = client.get("/dashboard", follow_redirects=False)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/"


def test_dashboard_sin_sesion_termina_en_login(client):
    respuesta = client.get("/dashboard", follow_redirects=True)
    assert respuesta.status_code == 200
    assert "INICIAR SESIÓN" in respuesta.get_data(as_text=True).upper()


def test_dashboard_con_sesion_siembra_inventario(client, app, creador_usuarios, iniciar_sesion):
    from mi_app.extensions import db
    from mi_app.models import ArticuloInventario

    creador_usuarios("ana")
    iniciar_sesion("ana")

    respuesta = client.get("/dashboard")
    assert respuesta.status_code == 200

    with app.app_context():
        assert db.session.query(ArticuloInventario).count() == 6


def test_docs_devuelve_rutas(client):
    respuesta = client.get("/docs")
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert "rutas" in datos
    rutas = {ruta["ruta"] for ruta in datos["rutas"]}
    assert "/api/login" in rutas
    assert "/api/inventario/" in rutas