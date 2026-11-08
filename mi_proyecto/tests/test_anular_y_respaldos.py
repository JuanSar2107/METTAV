"""Corregir sin borrar (anular y dar de baja), copias de seguridad y permisos."""

import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook

from mi_app.exportar import respuesta_excel
from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario, RegistroAuditoria, Remision, SalidaIntegrada
from mi_app.respaldos import carpetas_de_archivos, crear_respaldo, restaurar_respaldo


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")


def _articulo(app, codigo="ZF-EQ-CO-001", stock=10, **campos):
    with app.app_context():
        articulo = ArticuloInventario(
            codigo=codigo, nombre=f"Artículo {codigo}", categoria="General", descripcion="d", stock=stock,
            stock_maximo=stock, unidad="unidades", ubicacion="Bodega", imagen_url="/x.png", **campos,
        )
        db.session.add(articulo)
        db.session.commit()
        return articulo.id


def _stock(app, id_articulo):
    with app.app_context():
        return db.session.get(ArticuloInventario, id_articulo).stock


def _anular(client, id_movimiento, motivo="Error de digitación"):
    return client.post(f"/api/inventario/movimientos/{id_movimiento}/anular", json={"motivo": motivo})


def _retirar(client, id_articulo, cantidad=3):
    respuesta = client.post(f"/api/inventario/{id_articulo}/retirar", json={"cantidad": cantidad})
    assert respuesta.status_code == 200
    return respuesta.get_json()["movimiento"]["id"]


def _remision(client, id_articulo, cantidad=2):
    return client.post("/api/remisiones", json={
        "cliente_nombre": "Cliente", "cliente_nit": "900.059.427-0",
        "lineas": [{"id": id_articulo, "cantidad": cantidad, "estado_servicio": "Entregado"}],
    })


def test_anular_retiro_devuelve_stock_y_deja_constancia(client, app, admin):
    id_articulo = _articulo(app)
    id_movimiento = _retirar(client, id_articulo)
    assert _stock(app, id_articulo) == 7

    assert _anular(client, id_movimiento).status_code == 200
    assert _stock(app, id_articulo) == 10
    with app.app_context():
        movimiento = db.session.get(MovimientoInventario, id_movimiento)
        assert movimiento.anulado_por == "admin"
        assert movimiento.motivo_anulacion == "Error de digitación"
        assert RegistroAuditoria.query.filter_by(accion="Anular movimiento").count() == 1


def test_no_se_anula_dos_veces(client, app, admin):
    id_articulo = _articulo(app)
    id_movimiento = _retirar(client, id_articulo)
    _anular(client, id_movimiento)
    assert _anular(client, id_movimiento).status_code == 409
    assert _stock(app, id_articulo) == 10


def test_anular_exige_motivo_y_admin(client, app, creador_usuarios, iniciar_sesion):
    id_articulo = _articulo(app)
    creador_usuarios("admin", es_admin=True)
    creador_usuarios("aux", es_auxiliar=True)
    iniciar_sesion("admin")
    id_movimiento = _retirar(client, id_articulo)
    assert _anular(client, id_movimiento, "   ").status_code == 400
    iniciar_sesion("aux")
    assert _anular(client, id_movimiento).status_code == 403
    assert _stock(app, id_articulo) == 7


def test_anular_ingreso_sin_unidades_no_cambia_nada(client, app, admin):
    id_articulo = _articulo(app, stock=1)
    ingreso = client.post(f"/api/inventario/{id_articulo}/ingresar", json={"cantidad": 5}).get_json()["movimiento"]["id"]
    _retirar(client, id_articulo, 6)
    assert _anular(client, ingreso).status_code == 409
    assert _stock(app, id_articulo) == 0
    with app.app_context():
        assert db.session.get(MovimientoInventario, ingreso).anulado_en is None


def test_anular_una_linea_anula_toda_la_salida(client, app, admin):
    equipo, parte = _articulo(app, "ZF-EQ-CO-001"), _articulo(app, "ZF-EQ-CO-002")
    salida = client.post("/api/inventario/salidas-integradas", json={
        "principal": {"id": equipo, "cantidad": 1},
        "componentes": [{"id": parte, "cantidad": 4}],
        "proceso": "Reparación" if False else None,
    })
    # El proceso válido se toma de la lista oficial para no atar el test a un texto.
    from mi_app.models.inventory import PROCESOS_INTEGRACION
    salida = client.post("/api/inventario/salidas-integradas", json={
        "principal": {"id": equipo, "cantidad": 1},
        "componentes": [{"id": parte, "cantidad": 4}],
        "proceso": PROCESOS_INTEGRACION[0],
    })
    assert salida.status_code == 201
    datos = salida.get_json()["salida"]

    assert _anular(client, datos["movimientos"][1]["id"]).get_json()["anulados"] == 2
    assert (_stock(app, equipo), _stock(app, parte)) == (10, 10)
    with app.app_context():
        assert db.session.get(SalidaIntegrada, datos["id"]).anulado_en is not None


def test_anular_remision_restaura_estado_y_marca_el_documento(client, app, admin):
    id_articulo = _articulo(app, estado_servicio="En proceso")
    creada = _remision(client, id_articulo)
    assert creada.status_code == 201
    id_remision = creada.get_json()["remision"]["id"]
    with app.app_context():
        id_movimiento = MovimientoInventario.query.filter_by(id_remision=id_remision).one().id
        assert db.session.get(ArticuloInventario, id_articulo).estado_servicio == "Entregado"

    assert _anular(client, id_movimiento).status_code == 200
    assert _stock(app, id_articulo) == 10
    with app.app_context():
        assert db.session.get(ArticuloInventario, id_articulo).estado_servicio == "En proceso"
        assert db.session.get(Remision, id_remision).anulado_en is not None
    assert "REMISIÓN ANULADA" in client.get(f"/remisiones/{id_remision}").get_data(as_text=True)
    # El consecutivo de una remisión anulada no se reutiliza.
    siguiente = _remision(client, id_articulo).get_json()["remision"]
    assert siguiente["consecutivo"] == 2


def test_reporte_no_suma_anulados(client, app, admin):
    id_articulo = _articulo(app)
    id_movimiento = _retirar(client, id_articulo, 3)
    _retirar(client, id_articulo, 1)
    _anular(client, id_movimiento)
    resumen = client.get("/api/reportes/movimientos").get_json()["resumen"]
    assert (resumen["retiros"], resumen["unidades_retiradas"], resumen["anulados"]) == (1, 1, 1)


def test_articulo_con_historial_se_da_de_baja(client, app, admin):
    id_articulo = _articulo(app)
    _retirar(client, id_articulo, 1)
    respuesta = client.delete(f"/api/inventario/{id_articulo}", json={"motivo": "Dañado"})
    assert respuesta.get_json()["baja"] is True
    with app.app_context():
        articulo = db.session.get(ArticuloInventario, id_articulo)
        assert articulo.motivo_baja == "Dañado"
        assert articulo.stock == 9

    assert client.post(f"/api/inventario/{id_articulo}/retirar", json={"cantidad": 1}).status_code == 404
    assert client.post(f"/api/inventario/{id_articulo}/ingresar", json={"cantidad": 1}).status_code == 404
    assert _remision(client, id_articulo).status_code == 404
    assert client.get("/api/reportes/inventario").get_json()["total"] == 0
    assert 'data-code="ZF-EQ-CO-001"' not in client.get("/dashboard").get_data(as_text=True)
    assert client.get("/api/inventario/trazabilidad/ZF-EQ-CO-001").get_json()["articulo"]["dado_de_baja"] is True
    assert client.get("/api/reportes/bajas").get_json()["total"] == 1


def test_baja_bloquea_anular_hasta_reactivar(client, app, admin):
    id_articulo = _articulo(app)
    id_movimiento = _retirar(client, id_articulo, 1)
    client.delete(f"/api/inventario/{id_articulo}")
    assert _anular(client, id_movimiento).status_code == 409

    assert client.post(f"/api/inventario/{id_articulo}/reactivar").status_code == 200
    assert client.post(f"/api/inventario/{id_articulo}/reactivar").status_code == 409
    assert _anular(client, id_movimiento).status_code == 200
    assert _stock(app, id_articulo) == 10
    assert client.get("/api/reportes/inventario").get_json()["total"] == 1


def test_articulo_sin_historial_se_borra(client, app, admin):
    id_articulo = _articulo(app)
    assert client.delete(f"/api/inventario/{id_articulo}").get_json()["baja"] is False
    with app.app_context():
        assert db.session.get(ArticuloInventario, id_articulo) is None


def _carpetas(tmp_path):
    return carpetas_de_archivos(tmp_path / "docs", tmp_path / "imagenes")


def test_respaldo_y_restauracion_recuperan_datos_y_archivos(app, tmp_path):
    id_articulo = _articulo(app)
    carpetas = _carpetas(tmp_path)
    carpetas["documentos"].mkdir(parents=True)
    (carpetas["documentos"] / "soporte.pdf").write_bytes(b"pdf")
    url = app.config["SQLALCHEMY_DATABASE_URI"]

    copia = crear_respaldo(url, tmp_path / "copias", carpetas)
    with app.app_context():
        db.session.delete(db.session.get(ArticuloInventario, id_articulo))
        db.session.commit()
    (carpetas["documentos"] / "soporte.pdf").unlink()

    copiadas = restaurar_respaldo(copia, url, carpetas)
    assert copiadas["articulos_inventario"] == 1
    assert _stock(app, id_articulo) == 10
    assert (carpetas["documentos"] / "soporte.pdf").read_bytes() == b"pdf"


def test_restaurar_no_sale_de_las_carpetas(app, tmp_path):
    url = app.config["SQLALCHEMY_DATABASE_URI"]
    carpetas = _carpetas(tmp_path)
    copia = crear_respaldo(url, tmp_path / "copias", carpetas)
    with zipfile.ZipFile(copia, "a") as archivo:
        archivo.writestr("documentos/../../escapado.txt", "x")
        archivo.writestr("otra_carpeta/malo.txt", "x")
    restaurar_respaldo(copia, url, carpetas)
    assert not list(tmp_path.rglob("escapado.txt"))
    assert not list(tmp_path.rglob("malo.txt"))


def test_restaurar_rechaza_un_zip_ajeno(app, tmp_path):
    ajeno = tmp_path / "ajeno.zip"
    with zipfile.ZipFile(ajeno, "w") as archivo:
        archivo.writestr("cualquiera.txt", "x")
    with pytest.raises(ValueError):
        restaurar_respaldo(ajeno, app.config["SQLALCHEMY_DATABASE_URI"], _carpetas(tmp_path))


def test_respaldo_conserva_solo_las_ultimas(app, tmp_path):
    carpeta = tmp_path / "copias"
    carpeta.mkdir()
    for dia in range(1, 6):
        (carpeta / f"mettav-respaldo-2026-01-0{dia}-000000.zip").write_bytes(b"x")
    (carpeta / "mettav-antes-de-restaurar-2026-01-01-000000.zip").write_bytes(b"x")
    crear_respaldo(app.config["SQLALCHEMY_DATABASE_URI"], carpeta, _carpetas(tmp_path), conservar=2)
    nombres = sorted(ruta.name for ruta in carpeta.glob("*.zip"))
    assert len(nombres) == 3
    assert "mettav-antes-de-restaurar-2026-01-01-000000.zip" in nombres
    assert "mettav-respaldo-2026-01-05-000000.zip" in nombres


def test_descargar_respaldo_solo_admin(client, app, creador_usuarios, iniciar_sesion):
    assert client.post("/api/reportes/respaldo").status_code == 401
    creador_usuarios("aux", es_auxiliar=True)
    iniciar_sesion("aux")
    assert client.post("/api/reportes/respaldo").status_code == 403
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")
    respuesta = client.post("/api/reportes/respaldo")
    assert respuesta.status_code == 200
    with zipfile.ZipFile(BytesIO(respuesta.data)) as archivo:
        assert "base_de_datos.sqlite3" in archivo.namelist()
    with app.app_context():
        assert RegistroAuditoria.query.filter_by(accion="Descargar copia de seguridad").count() == 1


def test_excel_no_ejecuta_formulas(app):
    with app.test_request_context():
        respuesta = respuesta_excel("T", ["A"], [['=HYPERLINK("http://malo","x")']], "t")
        respuesta.direct_passthrough = False
        hoja = load_workbook(BytesIO(respuesta.get_data())).active
    assert hoja["A2"].data_type == "s"


def test_empleado_no_ve_remisiones_ni_salidas_ajenas(client, app, creador_usuarios, iniciar_sesion):
    from mi_app.models.inventory import PROCESOS_INTEGRACION

    id_articulo = _articulo(app)
    creador_usuarios("admin", es_admin=True)
    creador_usuarios("empleado")
    iniciar_sesion("admin")
    id_remision = _remision(client, id_articulo, 1).get_json()["remision"]["id"]
    id_salida = client.post("/api/inventario/salidas-integradas", json={
        "componentes": [{"id": id_articulo, "cantidad": 1}], "referencia": "Equipo",
        "proceso": PROCESOS_INTEGRACION[0],
    }).get_json()["salida"]["id"]

    iniciar_sesion("empleado")
    assert client.get(f"/remisiones/{id_remision}").status_code == 404
    assert client.get("/api/remisiones").get_json()["total"] == 0
    assert client.get(f"/api/inventario/salidas-integradas/{id_salida}").status_code == 404


def test_docs_requiere_sesion(client, creador_usuarios, iniciar_sesion):
    assert client.get("/docs").status_code == 401
    creador_usuarios("empleado")
    iniciar_sesion("empleado")
    assert client.get("/docs").status_code == 200
