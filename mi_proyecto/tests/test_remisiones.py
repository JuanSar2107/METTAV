"""Tests del estado del servicio (R5) y las remisiones de salida (R8)."""

from decimal import Decimal

import pytest

from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario, RegistroAuditoria, Remision


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True, nombre_completo="Jefa de Bodega")
    iniciar_sesion("admin")


@pytest.fixture()
def mercancia(app):
    """Mercancía de un cliente (grupo 004) que ingresó para reparación."""
    datos = [
        ("SER-2026-09-29-BOM", "Bomba de aceite", "8413.30.10.00", Decimal("1200.00"), 1),
        ("SER-2026-09-29-ARR", "Arrancador neumático", "8412.90.00.00", Decimal("1000.00"), 1),
        ("SER-2026-09-29-ACC", "Caja de accesorios", None, None, 3),
    ]
    with app.app_context():
        ids = []
        for codigo, nombre, subpartida, fob, stock in datos:
            articulo = ArticuloInventario(
                codigo=codigo, nombre=nombre, categoria="Maquinaria", descripcion=nombre, grupo="004",
                stock=stock, stock_maximo=stock, unidad="unidades", ubicacion="Bodega", imagen_url="x.png",
                subpartida=subpartida, valor_fob_usd=fob, procedencia="Nacional", estado="Para reparación",
                tipo_servicio="Reparación", estado_servicio="En servicio",
            )
            db.session.add(articulo)
            db.session.flush()
            ids.append(articulo.id)
        db.session.commit()
        return ids


def _cliente(**extra):
    return {
        "cliente_nombre": "MOTORKAM COMPANY S.A.S",
        "cliente_nit": "900.059.427-0",
        "contacto": "3012752144",
        "email": "contacto@ejemplo.com",
        "tipo_servicio": "Mantenimiento",
        **extra,
    }


# --- R5: estado del servicio -------------------------------------------------

def test_actualizar_servicio_audita_el_cambio(client, app, admin, mercancia):
    respuesta = client.patch(
        f"/api/inventario/{mercancia[0]}/servicio",
        json={"cliente": "MOTORKAM", "tipo_servicio": "Reparación", "estado_servicio": "Terminado"},
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["cambios"] == 2
    with app.app_context():
        articulo = db.session.get(ArticuloInventario, mercancia[0])
        assert (articulo.cliente, articulo.estado_servicio) == ("MOTORKAM", "Terminado")
        registro = RegistroAuditoria.query.filter_by(accion="Actualizar servicio").one()
        assert "estado: En servicio → Terminado" in registro.detalle


@pytest.mark.parametrize("datos", [{"estado_servicio": "Perdido"}, {"tipo_servicio": "Pintura"}, {"cliente": "x" * 161}])
def test_actualizar_servicio_valida(client, admin, mercancia, datos):
    assert client.patch(f"/api/inventario/{mercancia[0]}/servicio", json=datos).status_code == 400


def test_actualizar_servicio_requiere_admin(client, creador_usuarios, iniciar_sesion, mercancia):
    creador_usuarios("normal")
    iniciar_sesion("normal")
    assert client.patch(f"/api/inventario/{mercancia[0]}/servicio", json={}).status_code == 403


def test_reporte_inventario_filtra_por_estado_del_servicio(client, admin, mercancia):
    client.patch(f"/api/inventario/{mercancia[0]}/servicio", json={"tipo_servicio": "Reparación", "estado_servicio": "Terminado"})
    filas = client.get("/api/reportes/inventario?estado_servicio=Terminado").get_json()["filas"]
    assert [f["codigo"] for f in filas] == ["SER-2026-09-29-BOM"]
    assert filas[0]["tipo_servicio"] == "Reparación"


# --- R8: remisión de salida --------------------------------------------------

def test_crear_remision_descuenta_y_deja_trazabilidad(client, app, admin, mercancia):
    bomba, arrancador, accesorios = mercancia
    respuesta = client.post("/api/remisiones", json=_cliente(
        formulario="1383926",
        lineas=[
            {"id": bomba, "cantidad": 1},
            {"id": accesorios, "cantidad": 2, "estado_servicio": "Cancelado"},
        ],
    ))
    assert respuesta.status_code == 201
    datos = respuesta.get_json()
    remision = datos["remision"]
    assert remision["numero"] == "REM-0001"
    assert datos["url"] == f"/remisiones/{remision['id']}"
    assert [(l["codigo"], l["cantidad"], l["estado_servicio"]) for l in remision["lineas"]] == [
        ("SER-2026-09-29-BOM", 1, "Entregado"),
        ("SER-2026-09-29-ACC", 2, "Cancelado"),
    ]
    assert remision["lineas"][0]["subpartida"] == "8413.30.10.00"
    assert remision["lineas"][0]["valor_fob_usd"] == 1200.0

    with app.app_context():
        assert db.session.get(ArticuloInventario, bomba).stock == 0
        assert db.session.get(ArticuloInventario, accesorios).stock == 1
        assert db.session.get(ArticuloInventario, bomba).estado_servicio == "Entregado"
        assert db.session.get(ArticuloInventario, bomba).cliente == "MOTORKAM COMPANY S.A.S"
        assert db.session.get(ArticuloInventario, arrancador).stock == 1
        movimiento = MovimientoInventario.query.filter_by(codigo_articulo="SER-2026-09-29-BOM").one()
        assert (movimiento.tipo, movimiento.origen, movimiento.formulario) == ("Retiro", "Remisión", "1383926")
        assert movimiento.observaciones == "Remisión REM-0001 · MOTORKAM COMPANY S.A.S"
        assert movimiento.id_remision == remision["id"]


def test_consecutivo_aumenta(client, admin, mercancia):
    for i, id_articulo in enumerate(mercancia[:2], start=1):
        datos = client.post("/api/remisiones", json=_cliente(lineas=[{"id": id_articulo, "cantidad": 1}])).get_json()
        assert datos["remision"]["numero"] == f"REM-{i:04d}"


def test_remision_sin_stock_no_descuenta_nada(client, app, admin, mercancia):
    respuesta = client.post("/api/remisiones", json=_cliente(lineas=[
        {"id": mercancia[0], "cantidad": 1},
        {"id": mercancia[1], "cantidad": 5},
    ]))
    assert respuesta.status_code == 409
    with app.app_context():
        assert db.session.get(ArticuloInventario, mercancia[0]).stock == 1
        assert Remision.query.count() == 0
        assert MovimientoInventario.query.count() == 0


@pytest.mark.parametrize("cambios, mensaje", [
    ({"cliente_nombre": ""}, "nombre del cliente"),
    ({"cliente_nit": "abc"}, "NIT"),
    ({"email": "no-es-correo"}, "correo"),
    ({"tipo_servicio": "Pintura"}, "tipo de servicio"),
    ({"fecha": "27/10/2026"}, "fecha"),
    ({"formulario": "form 1"}, "Sizfra"),
    ({"lineas": []}, "al menos un artículo"),
    ({"lineas": [{"id": 1, "cantidad": 1, "estado_servicio": "Perdido"}]}, "estado del servicio"),
])
def test_remision_validaciones(client, admin, mercancia, cambios, mensaje):
    datos = _cliente(lineas=[{"id": mercancia[0], "cantidad": 1}])
    datos.update(cambios)
    respuesta = client.post("/api/remisiones", json=datos)
    assert respuesta.status_code == 400
    assert mensaje in respuesta.get_json()["error"]


def test_remision_requiere_sesion(client):
    assert client.post("/api/remisiones", json=_cliente(lineas=[])).status_code == 401
    assert client.get("/api/remisiones").status_code == 401
    respuesta = client.get("/remisiones/1")
    assert respuesta.status_code == 302


def test_listar_y_ver_remision_imprimible(client, admin, mercancia):
    creada = client.post("/api/remisiones", json=_cliente(
        fecha="2026-10-27", operacion_sizfra="420", lineas=[{"id": mercancia[0], "cantidad": 1}],
    )).get_json()["remision"]

    lista = client.get("/api/remisiones?cliente=900.059").get_json()
    assert lista["total"] == 1
    assert client.get("/api/remisiones?desde=2026-10-28").get_json()["total"] == 0

    html = client.get(f"/remisiones/{creada['id']}").get_data(as_text=True)
    assert "REM-0001" in html
    assert "27/10/2026" in html
    assert "MOTORKAM COMPANY S.A.S" in html
    assert "8413.30.10.00" in html
    assert "1,200.00" in html
    assert "Op. 420" in html
    assert client.get("/remisiones/999").status_code == 404


def test_remision_conserva_datos_aunque_se_elimine_el_articulo(client, app, admin, mercancia):
    creada = client.post("/api/remisiones", json=_cliente(lineas=[{"id": mercancia[0], "cantidad": 1}])).get_json()
    assert client.delete(f"/api/inventario/{mercancia[0]}").status_code == 200
    html = client.get(creada["url"]).get_data(as_text=True)
    assert "Bomba de aceite" in html


def test_dashboard_tiene_remision_y_servicio(client, admin, mercancia):
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="open-remission"' in html
    assert 'id="service-form"' in html
    assert 'class="service-label service-label--en-servicio"' in html
