"""Cambios pedidos en la reunión de bodega: subpartida sin puntos, propietario,
varios seriales, inventario general y para qué se usó lo retirado."""

import pytest

from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario
from mi_app.zona_franca import leer_seriales, resumen_seriales

BASE = {
    "nombre": "Reductor de rotor principal",
    "categoria": "Equipos",
    "descripcion": "Reductor para mantenimiento.",
    "stock": "3",
    "unidad": "unidades",
    "ubicacion": "Bodega",
}


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")


def _crear(client, campos=None, seriales=()):
    datos = [(clave, valor) for clave, valor in {**BASE, **(campos or {})}.items()]
    datos += [("serial", serial) for serial in seriales]
    from werkzeug.datastructures import MultiDict
    return client.post("/api/inventario/", data=MultiDict(datos), content_type="multipart/form-data")


def _articulo(app, nombre=BASE["nombre"]):
    with app.app_context():
        articulo = ArticuloInventario.query.filter_by(nombre=nombre).one()
        db.session.expunge(articulo)
        return articulo


@pytest.mark.parametrize("escrita, guardada", [
    ("8807300000", "8807300000"),
    ("8807.30.00.00", "8807300000"),
    ("8413", "8413"),
    ("841330100", "841330100"),
    ("88073000001", "88073000001"),
])
def test_subpartida_con_o_sin_puntos(client, app, admin, escrita, guardada):
    assert _crear(client, {"subpartida": escrita}).status_code == 201
    assert _articulo(app).subpartida == guardada


@pytest.mark.parametrize("escrita", ["841", "880730000012", "84-13", "84A3"])
def test_subpartida_invalida(client, admin, escrita):
    respuesta = _crear(client, {"subpartida": escrita})
    assert respuesta.status_code == 400
    assert "de 4 a 11 números" in respuesta.get_json()["error"]


def test_varios_seriales(client, app, admin):
    assert _crear(client, seriales=["SN-001", "", "SN-002", "sn-001", "SN-003"]).status_code == 201
    articulo = _articulo(app)
    assert articulo.lista_seriales == ["SN-001", "SN-002", "SN-003"]
    assert articulo.serial == "SN-001, SN-002, SN-003"


def test_seriales_en_celda_y_resumen_corto():
    assert leer_seriales({"serial": "A1, A2; A3\nA4"}) == ["A1", "A2", "A3", "A4"]
    assert leer_seriales({"serial": "N/A"}) == []
    resumen = resumen_seriales([f"SERIAL-LARGO-{n:04d}" for n in range(30)])
    assert len(resumen) <= 80 and resumen.endswith("más")


def test_serial_demasiado_largo(client, admin):
    assert _crear(client, seriales=["X" * 81]).status_code == 400


def test_serial_antiguo_se_sigue_viendo(app):
    articulo = ArticuloInventario(serial="B-77")
    assert articulo.lista_seriales == ["B-77"]


def test_propietario_cliente_exige_nombre(client, admin):
    respuesta = _crear(client, {"propietario": "cliente"})
    assert respuesta.status_code == 400
    assert "cliente" in respuesta.get_json()["error"]


def test_propietario_cliente_y_empresa(client, app, admin):
    assert _crear(client, {"propietario": "cliente", "cliente": "Helicentro Perú S.A.C",
                           "tipo_servicio": "Mantenimiento"}).status_code == 201
    articulo = _articulo(app)
    assert articulo.cliente == "Helicentro Perú S.A.C"
    assert articulo.propietario == "Helicentro Perú S.A.C"

    # Un activo de la empresa no guarda cliente ni servicio aunque el formulario los traiga.
    assert _crear(client, {"nombre": "Pulidora", "propietario": "empresa", "cliente": "X",
                           "tipo_servicio": "Mantenimiento", "responsable": "Medina"}).status_code == 201
    pulidora = _articulo(app, "Pulidora")
    assert pulidora.cliente is None and pulidora.tipo_servicio is None
    assert pulidora.propietario == "Activo de la empresa"
    assert pulidora.responsable == "Medina"


def test_grupo_004_sin_cliente(app):
    assert ArticuloInventario(grupo="004").propietario == "Cliente sin indicar"


def test_tablero_muestra_propietario_seriales_y_vista_general(client, app, admin):
    _crear(client, {"propietario": "cliente", "cliente": "Aviatrans"}, seriales=["R-1", "R-2"])
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'data-owner="Aviatrans"' in html
    assert "data-serials='[\"R-1\", \"R-2\"]'" in html
    assert 'id="general-inventory"' in html
    assert '<option value="Aviatrans">Aviatrans</option>' in html


def test_retiro_guarda_para_que_se_uso_y_ultima_salida(client, app, admin):
    _crear(client, {"nombre": "Combustible Jet A1", "unidad": "galones", "stock": "50"})
    articulo = _articulo(app, "Combustible Jet A1")
    respuesta = client.post(f"/api/inventario/{articulo.id}/retirar", json={
        "cantidad": 10, "destino": "Pruebas del control de combustible de Helicentro Perú",
    })
    assert respuesta.status_code == 200
    assert respuesta.get_json()["movimiento"]["destino"] == "Pruebas del control de combustible de Helicentro Perú"
    with app.app_context():
        retiro = MovimientoInventario.query.filter_by(tipo="Retiro").one()
        assert retiro.destino.startswith("Pruebas")

    html = client.get("/dashboard").get_data(as_text=True)
    assert "10 galones · " in html
    assert "por admin · para Pruebas del control de combustible de Helicentro Perú" in html

    excel = client.get("/api/inventario/movimientos?formato=xlsx")
    assert excel.status_code == 200


def test_destino_demasiado_largo(client, app, admin):
    _crear(client)
    articulo = _articulo(app)
    respuesta = client.post(f"/api/inventario/{articulo.id}/retirar", json={"cantidad": 1, "destino": "x" * 161})
    assert respuesta.status_code == 400
