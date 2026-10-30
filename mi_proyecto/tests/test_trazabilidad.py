"""Tests de trazabilidad (R6): datos del activo, observaciones, origen y auditoría."""

from datetime import date
from io import BytesIO

import pytest
from openpyxl import Workbook

from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario, RegistroAuditoria
from mi_app.zona_franca import leer_fecha


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True, nombre_completo="Jefa de Bodega")
    iniciar_sesion("admin")


def _excel(filas):
    """Excel con las mismas columnas de trazabilidad que el de METTAV (incluidos los dos 'Documento soporte')."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Inventario Equipos"
    hoja.append([
        "Código interno", "Codigo ZF ", "Descripción", "Serial", "CANT", "Responsable", "Estado",
        "Fecha de Ingreso", "Documento Soporte", "Fecha de Retiro", "Documento soporte ",
        "razones por las cuales se retira",
    ])
    for fila in filas:
        hoja.append(fila)
    bufer = BytesIO()
    libro.save(bufer)
    bufer.seek(0)
    return bufer


def _importar(client, archivo):
    return client.post(
        "/api/inventario/importar",
        data={"archivo": (archivo, "inventario.xlsx")},
        content_type="multipart/form-data",
    )


@pytest.mark.parametrize("valor, esperado", [
    ("08 de mayo del 2026", date(2026, 5, 8)),
    ("8 de mayo del 2026 ", date(2026, 5, 8)),
    ("23 de julio de 2026", date(2026, 7, 23)),
    ("5 de Septiembre del 2026", date(2026, 9, 5)),
    ("2026-08-05", date(2026, 8, 5)),
    ("05/08/2026", date(2026, 8, 5)),
    ("", None),
    (None, None),
])
def test_leer_fecha(valor, esperado):
    assert leer_fecha(valor) == esperado


@pytest.mark.parametrize("valor", ["31 de febrero del 2026", "mañana", "8 de mayu del 2026"])
def test_leer_fecha_invalida(valor):
    with pytest.raises(ValueError):
        leer_fecha(valor)


def test_importar_columnas_de_trazabilidad(client, app, admin):
    archivo = _excel([
        ["EL-APT-CO-001", "ZF-EL-CO-001", "TV de 50\"", "HYLED4313", 1, "Directores", "Bueno",
         "08 de mayo del 2026", "remision No 0001 aviatrans", "10/10/2026", "acta 7", "Se dañó"],
        ["MO-APT-CO-002", "ZF-MO-CO-002", "Sillones", "N/A", 2, "Operativos", "Bueno",
         "fecha rara", None, None, None, None],
    ])
    datos = _importar(client, archivo).get_json()
    assert datos["creados"] == 2
    # La fecha ilegible no deja la fila por fuera: se importa sin ese dato y se avisa.
    assert [(a["fila"], a["codigo"]) for a in datos["avisos"]] == [(3, "ZF-MO-CO-002")]

    with app.app_context():
        tv = ArticuloInventario.query.filter_by(codigo="ZF-EL-CO-001").one()
        assert tv.serial == "HYLED4313"
        assert tv.responsable == "Directores"
        assert tv.fecha_ingreso == date(2026, 5, 8)
        assert tv.documento_soporte == "remision No 0001 aviatrans"
        # La segunda columna "Documento soporte" es la del retiro.
        assert (tv.fecha_retiro, tv.documento_retiro, tv.razon_retiro) == (date(2026, 10, 10), "acta 7", "Se dañó")
        sillones = ArticuloInventario.query.filter_by(codigo="ZF-MO-CO-002").one()
        assert (sillones.serial, sillones.fecha_ingreso, sillones.stock) == (None, None, 2)

        movimiento = MovimientoInventario.query.filter_by(codigo_articulo="ZF-EL-CO-001").one()
        assert movimiento.origen == "Importación Excel"
        resumen = RegistroAuditoria.query.filter_by(accion="Importar Excel").one()
        assert "2 creados" in resumen.detalle


def test_reimportar_audita_los_campos_que_cambian(client, app, admin):
    fila = ["EL-APT-CO-001", "ZF-EL-CO-001", "TV", "S1", 1, "Directores", "Bueno", None, None, None, None, None]
    _importar(client, _excel([fila]))
    _importar(client, _excel([fila]))  # sin cambios: no deja registro por artículo
    fila[5] = "Operativos"
    _importar(client, _excel([fila]))
    with app.app_context():
        registros = RegistroAuditoria.query.filter_by(accion="Actualizar por importación").all()
        assert [r.detalle for r in registros] == ["Campos: responsable"]


def test_retiro_e_ingreso_guardan_observaciones_y_origen(client, app, admin):
    with app.app_context():
        articulo = ArticuloInventario(
            codigo="ZF-MAQ-CO-001", nombre="Banco", categoria="Maquinaria", descripcion="Banco",
            stock=2, stock_maximo=2, unidad="unidades", ubicacion="Bodega", imagen_url="x.png",
        )
        db.session.add(articulo)
        db.session.commit()
        id_articulo = articulo.id

    respuesta = client.post(
        f"/api/inventario/{id_articulo}/retirar",
        json={"cantidad": 1, "observaciones": "  Para mantenimiento  "},
    )
    movimiento = respuesta.get_json()["movimiento"]
    assert (movimiento["origen"], movimiento["observaciones"]) == ("Manual", "Para mantenimiento")
    assert client.post(
        f"/api/inventario/{id_articulo}/retirar", json={"cantidad": 1, "observaciones": "x" * 2001},
    ).status_code == 400


def test_trazabilidad_de_un_articulo_incluye_movimientos_y_auditoria(client, app, admin, imagen_png):
    client.post(
        "/api/inventario/",
        data={
            "nombre": "Banco", "descripcion": "Banco hidráulico.", "stock": "3", "codigo": "ZF-MAQ-CO-001",
            "serial": "B-77", "responsable": "Operativos", "fecha_ingreso": "2026-05-08",
            "documento_soporte": "Remisión 0001", "imagen": (BytesIO(imagen_png), "imagen.png"),
        },
        content_type="multipart/form-data",
    )
    with app.app_context():
        id_articulo = ArticuloInventario.query.filter_by(codigo="ZF-MAQ-CO-001").one().id
    client.post(f"/api/inventario/{id_articulo}/retirar", json={"cantidad": 1, "formulario": "1383926"})

    datos = client.get("/api/inventario/trazabilidad/zf-maq-co-001").get_json()
    assert datos["articulo"]["serial"] == "B-77"
    assert datos["articulo"]["fecha_ingreso"] == "2026-05-08"
    clases = [(e["clase"], e.get("tipo") or e.get("accion")) for e in datos["eventos"]]
    assert clases == [("movimiento", "Retiro"), ("movimiento", "Ingreso"), ("auditoria", "Crear artículo")]
    assert datos["eventos"][0]["formulario"] == "1383926"
    assert datos["eventos"][2]["empleado"] == "Jefa de Bodega"


def test_trazabilidad_sobrevive_a_la_eliminacion(client, app, admin):
    with app.app_context():
        articulo = ArticuloInventario(
            codigo="ZF-OT-CO-001", nombre="Camilla", categoria="Otros", descripcion="Camilla",
            stock=4, stock_maximo=4, unidad="unidades", ubicacion="Operativa", imagen_url="x.png",
        )
        db.session.add(articulo)
        db.session.commit()
        id_articulo = articulo.id

    assert client.delete(f"/api/inventario/{id_articulo}").status_code == 200
    datos = client.get("/api/inventario/trazabilidad/ZF-OT-CO-001").get_json()
    assert datos["articulo"] is None
    assert datos["eventos"][0]["accion"] == "Eliminar artículo"
    assert "tenía 4 unidades" in datos["eventos"][0]["detalle"]


def test_trazabilidad_permisos_y_codigo_inexistente(client, creador_usuarios, iniciar_sesion):
    assert client.get("/api/inventario/trazabilidad/ZF-X").status_code == 401
    creador_usuarios("normal")
    iniciar_sesion("normal")
    assert client.get("/api/inventario/trazabilidad/ZF-X").status_code == 403
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")
    assert client.get("/api/inventario/trazabilidad/ZF-X").status_code == 404


def test_crear_articulo_rechaza_fecha_invalida(client, admin, imagen_png):
    respuesta = client.post(
        "/api/inventario/",
        data={
            "nombre": "Banco", "descripcion": "Banco.", "stock": "1", "fecha_ingreso": "ayer",
            "imagen": (BytesIO(imagen_png), "imagen.png"),
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 400
    assert "fecha" in respuesta.get_json()["error"]
