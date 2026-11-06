"""Tests de la edición de artículos y del límite de artículos del asistente."""

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest

from mi_app.extensions import db
from mi_app.models import ArticuloInventario, Categoria, MovimientoInventario, RegistroAuditoria
from mi_app.routes import assistant

BASE = {
    "nombre": "Mesa de lavado",
    "categoria": "Maquinaria",
    "descripcion": "Mesa de lavado de piezas.",
    "unidad": "unidades",
    "ubicacion": "Bodega",
}


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")


@pytest.fixture()
def mesa(app):
    with app.app_context():
        articulo = ArticuloInventario(
            codigo="ZF-MAQ-CO-205", codigo_interno="MAQ-BOD-CO-205", tipo="CO", nombre="MESA DE LAVADO",
            categoria="Maquinaria", descripcion="Mesa", stock=2, stock_maximo=4, unidad="unidades",
            ubicacion="Bodega", imagen_url="/static/images/workshop-bg.jpg", cliente="CLIENTE",
            estado_servicio="En servicio",
        )
        db.session.add(articulo)
        db.session.add(MovimientoInventario(
            empleado="Jefa", usuario="admin", articulo="MESA DE LAVADO", codigo_articulo="ZF-MAQ-CO-205",
            categoria="Maquinaria", tipo="Ingreso", cantidad=2, unidad="unidades",
        ))
        db.session.commit()
        return articulo.id


def _editar(client, id_articulo, **datos):
    return client.put(f"/api/inventario/{id_articulo}", data={**BASE, **datos}, content_type="multipart/form-data")


def test_editar_cambia_datos_y_conserva_codigo_stock_y_servicio(client, app, admin, mesa):
    respuesta = _editar(
        client, mesa, marca="Truper", subpartida="8413.30.10.00", valor_fob_usd="1200.00", grupo="002",
        fecha_ingreso="2026-05-08", codigo="ZF-MAQ-CO-999", stock="50", cliente="OTRO",
    )
    assert respuesta.status_code == 200
    with app.app_context():
        articulo = db.session.get(ArticuloInventario, mesa)
        assert articulo.nombre == "Mesa de lavado"
        assert articulo.marca == "Truper"
        assert articulo.valor_fob_usd == Decimal("1200.00")
        assert articulo.fecha_ingreso == date(2026, 5, 8)
        # No se editan aquí aunque lleguen en el formulario.
        assert (articulo.codigo, articulo.codigo_interno, articulo.tipo) == ("ZF-MAQ-CO-205", "MAQ-BOD-CO-205", "CO")
        assert (articulo.stock, articulo.stock_maximo) == (2, 4)
        assert (articulo.cliente, articulo.estado_servicio) == ("CLIENTE", "En servicio")
        # El historial conserva el nombre que tenía en ese momento.
        assert MovimientoInventario.query.one().articulo == "MESA DE LAVADO"
        registro = RegistroAuditoria.query.filter_by(accion="Editar artículo").one()
        assert registro.codigo_articulo == "ZF-MAQ-CO-205"
        assert "nombre" in registro.detalle and "marca" in registro.detalle


def test_editar_sin_cambios_no_deja_auditoria(client, app, admin, mesa):
    assert _editar(client, mesa).get_json()["cambios"] > 0
    assert _editar(client, mesa).get_json()["cambios"] == 0
    with app.app_context():
        assert RegistroAuditoria.query.filter_by(accion="Editar artículo").count() == 1


def test_editar_cambia_la_imagen(client, app, admin, mesa, imagen_png):
    primera = _editar(client, mesa, imagen=(BytesIO(imagen_png), "a.png"))
    assert primera.status_code == 200
    with app.app_context():
        url_primera = db.session.get(ArticuloInventario, mesa).imagen_url
    assert url_primera.startswith("/static/images/inventory/")
    ruta_primera = app.static_folder + url_primera.removeprefix("/static")
    assert open(ruta_primera, "rb").read()

    _editar(client, mesa, imagen=(BytesIO(imagen_png), "b.png"))
    with app.app_context():
        assert db.session.get(ArticuloInventario, mesa).imagen_url != url_primera
    # La foto anterior ya no ocupa espacio.
    with pytest.raises(FileNotFoundError):
        open(ruta_primera, "rb")


def test_editar_no_borra_la_imagen_por_defecto(client, app, admin, mesa, imagen_png):
    # La imagen compartida de la bodega está fuera de la carpeta de subidas.
    assert _editar(client, mesa, imagen=(BytesIO(imagen_png), "a.png")).status_code == 200
    from pathlib import Path

    assert (Path(app.root_path) / "static" / "images" / "workshop-bg.jpg").is_file()


@pytest.mark.parametrize("datos", [
    {"nombre": ""},
    {"descripcion": ""},
    {"subpartida": "84-13"},
    {"grupo": "009"},
    {"valor_fob_usd": "mil"},
    {"fecha_ingreso": "ayer"},
])
def test_editar_valida(client, app, admin, mesa, datos):
    assert _editar(client, mesa, **datos).status_code == 400
    with app.app_context():
        assert db.session.get(ArticuloInventario, mesa).nombre == "MESA DE LAVADO"


def test_imagen_invalida_no_cambia_nada(client, app, admin, mesa):
    respuesta = _editar(client, mesa, imagen=(BytesIO(b"no soy imagen"), "a.png"))
    assert respuesta.status_code == 400
    with app.app_context():
        assert db.session.get(ArticuloInventario, mesa).nombre == "MESA DE LAVADO"


def test_categoria_nueva_queda_registrada(client, app, admin, mesa):
    assert _editar(client, mesa, categoria="Bancos").status_code == 200
    with app.app_context():
        assert Categoria.query.filter_by(nombre="Bancos").count() == 1


def test_editar_solo_admin(client, mesa, creador_usuarios, iniciar_sesion):
    assert _editar(client, mesa).status_code == 401
    creador_usuarios("aux", es_auxiliar=True)
    iniciar_sesion("aux")
    assert _editar(client, mesa).status_code == 403
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="open-edit-item"' not in html and 'id="edit-item-dialog"' not in html


def test_editar_articulo_inexistente(client, admin):
    assert _editar(client, 9999).status_code == 404


def test_panel_admin_tiene_editar(client, admin, mesa):
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="open-edit-item"' in html and 'id="edit-item-dialog"' in html
    assert f'data-update-url="/api/inventario/{mesa}"' in html


def test_asistente_admite_el_inventario_completo():
    # El Excel tiene 312 ítems: no deben quedar por fuera.
    assert assistant._MAX_ARTICULOS >= 1000
