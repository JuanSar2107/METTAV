"""Traducción al inglés de los datos del inventario."""

import json

import pytest

from mi_app import gemini
from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario, TraduccionTexto

URL = "/api/traducciones/"


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")


@pytest.fixture()
def articulo(app):
    with app.app_context():
        db.session.add(ArticuloInventario(
            codigo="HER-001", nombre="Taladro", categoria="Herramientas", descripcion="Taladro azul", stock=1,
            stock_maximo=1, unidad="juegos", ubicacion="Estante", imagen_url="/x.png",
        ))
        db.session.commit()


@pytest.fixture()
def ia(monkeypatch):
    """Gemini simulado: antepone EN: a cada texto y cuenta las llamadas."""
    llamadas = []

    def consultar(_instrucciones, mensajes):
        lote = json.loads(mensajes[-1]["texto"])
        llamadas.append(lote)
        return json.dumps([f"EN: {texto}" for texto in lote])

    monkeypatch.setattr(gemini, "clave_configurada", lambda: True)
    monkeypatch.setattr(gemini, "consultar_gemini", consultar)
    return llamadas


def test_requiere_sesion(client):
    assert client.post(URL).status_code == 401


def test_traduce_guarda_y_no_repite(client, app, admin, articulo, ia):
    datos = client.post(URL).get_json()
    assert datos["traducciones"]["Taladro"] == "EN: Taladro"
    assert datos["traducciones"]["juegos"] == "EN: juegos"
    assert datos["pendientes"] == 0
    assert "HER-001" not in datos["traducciones"]

    assert client.post(URL).get_json()["traducciones"]["Taladro"] == "EN: Taladro"
    assert len(ia) == 1
    with app.app_context():
        assert TraduccionTexto.query.count() >= 5
        assert db.session.get(ArticuloInventario, 1).nombre == "Taladro"


def test_traduce_por_lotes(client, app, admin, ia):
    with app.app_context():
        for numero in range(45):
            db.session.add(ArticuloInventario(
                codigo=f"X-{numero}", nombre=f"Pieza {numero}", categoria="General", descripcion="Parte",
                stock=1, stock_maximo=1, unidad="unidades", ubicacion="Bodega", imagen_url="/x.png",
            ))
        db.session.commit()
    primero = client.post(URL).get_json()
    assert primero["pendientes"] > 0 and len(ia[0]) == 40
    assert client.post(URL).get_json()["pendientes"] == 0


def test_sin_clave_responde_lo_guardado(client, admin, articulo, monkeypatch):
    monkeypatch.setattr(gemini, "clave_configurada", lambda: False)
    datos = client.post(URL).get_json()
    assert datos["disponible"] is False and datos["traducciones"] == {}


@pytest.mark.parametrize("respuesta", ["no es json", '["solo uno"]', "[1, 2, 3, 4, 5, 6, 7, 8, 9]"])
def test_respuesta_mala_no_se_guarda(client, app, admin, articulo, monkeypatch, respuesta):
    monkeypatch.setattr(gemini, "clave_configurada", lambda: True)
    monkeypatch.setattr(gemini, "consultar_gemini", lambda *_: respuesta)
    assert client.post(URL).get_json()["disponible"] is False
    with app.app_context():
        assert TraduccionTexto.query.count() == 0


def test_error_de_gemini_no_rompe(client, admin, articulo, monkeypatch):
    def falla(*_):
        raise gemini.GeminiError("cuota")

    monkeypatch.setattr(gemini, "clave_configurada", lambda: True)
    monkeypatch.setattr(gemini, "consultar_gemini", falla)
    respuesta = client.post(URL)
    assert respuesta.status_code == 200 and respuesta.get_json()["disponible"] is False


def test_empleado_no_recibe_observaciones(client, app, creador_usuarios, iniciar_sesion, articulo, ia):
    with app.app_context():
        db.session.add(MovimientoInventario(
            empleado="Ana", usuario="ana", articulo="Taladro", codigo_articulo="HER-001", categoria="Herramientas",
            tipo="Retiro", cantidad=1, unidad="juegos", observaciones="Nota interna",
        ))
        db.session.commit()
    creador_usuarios("empleado")
    iniciar_sesion("empleado")
    assert "Nota interna" not in client.post(URL).get_json()["traducciones"]
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")
    assert "Nota interna" in client.post(URL).get_json()["traducciones"]
    assert "Ana" not in client.post(URL).get_json()["traducciones"]


def test_no_incluye_notas_de_remision_con_el_cliente(client, app, admin, articulo, ia):
    with app.app_context():
        db.session.add(MovimientoInventario(
            empleado="Ana", usuario="ana", articulo="Taladro", codigo_articulo="HER-001", categoria="Herramientas",
            tipo="Retiro", cantidad=1, unidad="juegos", observaciones="Remisión REM-0001 · ACME",
        ))
        db.session.commit()
    assert "Remisión REM-0001 · ACME" not in client.post(URL).get_json()["traducciones"]
