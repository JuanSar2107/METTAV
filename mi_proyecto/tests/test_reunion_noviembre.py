"""Tests de lo pedido el 06/11/2026: perfil auxiliar, códigos consecutivos e ingreso con documento soporte."""

from io import BytesIO

import pytest

from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario, Usuario

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")


@pytest.fixture()
def auxiliar(app, creador_usuarios, iniciar_sesion):
    creador_usuarios("aux", es_auxiliar=True)
    iniciar_sesion("aux")


@pytest.fixture()
def kit(app):
    with app.app_context():
        articulo = ArticuloInventario(
            codigo="SER-2026-09-29", nombre="Kit de componentes", categoria="Maquinaria", descripcion="Kit",
            stock=2, stock_maximo=2, unidad="unidades", ubicacion="Bodega", imagen_url="x.png",
        )
        db.session.add(articulo)
        db.session.commit()
        return articulo.id


def _crear(client, **datos):
    base = {"nombre": "Llave", "descripcion": "Llave de vaso.", "stock": "1"}
    return client.post("/api/inventario/", data={**base, **datos})


# --- Perfil auxiliar de inventarios -------------------------------------------

def test_admin_crea_usuario_auxiliar(client, app, admin):
    respuesta = client.post("/api/usuarios", json={"usuario": "laura", "contrasena": "clave-123", "rol": "auxiliar"})
    assert respuesta.status_code == 201
    assert respuesta.get_json()["usuario"]["rol"] == "auxiliar"
    with app.app_context():
        creado = Usuario.query.filter_by(usuario="laura").one()
        assert (creado.es_admin, creado.es_auxiliar, creado.rol_nombre) == (False, True, "Auxiliar de inventarios")


def test_no_se_puede_crear_un_admin_por_la_api(client, admin):
    respuesta = client.post("/api/usuarios", json={"usuario": "x", "contrasena": "clave-123", "rol": "admin"})
    assert respuesta.status_code == 400


def test_usuario_sin_rol_sigue_siendo_empleado(client, admin):
    respuesta = client.post("/api/usuarios", json={"usuario": "ana", "contrasena": "clave-123"})
    assert respuesta.get_json()["usuario"]["rol"] == "empleado"


def test_auxiliar_no_crea_codigos_ni_usuarios(client, auxiliar, kit):
    assert _crear(client).status_code == 403
    assert client.get("/api/inventario/siguiente-codigo?categoria=MAQ&ubicacion=BOD&tipo=CO").status_code == 403
    assert client.post(
        "/api/inventario/importar", data={"archivo": (BytesIO(b"x"), "a.xlsx")}, content_type="multipart/form-data",
    ).status_code == 403
    assert client.delete(f"/api/inventario/{kit}").status_code == 403
    assert client.post("/api/inventario/categorias", json={"nombre": "Nueva"}).status_code == 403
    assert client.get("/api/usuarios").status_code == 403
    assert client.post("/api/usuarios", json={"usuario": "x", "contrasena": "clave-123"}).status_code == 403


def test_auxiliar_opera_y_consulta(client, auxiliar, kit):
    assert client.post(f"/api/inventario/{kit}/ingresar", json={"cantidad": 1}).status_code == 200
    assert client.get("/api/inventario/movimientos").status_code == 200
    assert client.get("/api/reportes/inventario").status_code == 200
    assert client.get("/api/inventario/trazabilidad/SER-2026-09-29").status_code == 200
    assert client.patch(f"/api/inventario/{kit}/servicio", json={"estado_servicio": "Terminado"}).status_code == 200


def test_panel_segun_el_rol(client, auxiliar):
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="tab-btn-reports"' in html and 'id="tab-btn-movements"' in html and 'id="trace-dialog"' in html
    assert 'id="open-stock-entry"' in html
    assert 'id="open-add-item"' not in html
    assert 'id="tab-btn-users"' not in html
    assert 'id="section-users"' not in html
    assert "Auxiliar de inventarios" in html


def test_empleado_no_ve_historial_ni_reportes(client, creador_usuarios, iniciar_sesion, kit):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    assert client.get("/api/inventario/movimientos").status_code == 403
    assert client.get("/api/reportes/inventario").status_code == 403
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="tab-btn-reports"' not in html
    assert 'id="open-stock-entry"' in html


# --- Códigos consecutivos ------------------------------------------------------

def test_codigos_salen_consecutivos(client, app, admin):
    consulta = "/api/inventario/siguiente-codigo?categoria=MAQ&ubicacion=BOD&tipo=CO"
    assert client.get(consulta).get_json() == {"codigo": "ZF-MAQ-CO-001", "codigo_interno": "MAQ-BOD-CO-001"}

    datos = {"sigla_categoria": "MAQ", "sigla_ubicacion": "BOD", "tipo": "CO"}
    assert _crear(client, **datos).status_code == 201
    assert _crear(client, **datos).status_code == 201
    assert client.get(consulta).get_json()["codigo"] == "ZF-MAQ-CO-003"
    with app.app_context():
        segundo = ArticuloInventario.query.filter_by(codigo="ZF-MAQ-CO-002").one()
        assert segundo.codigo_interno == "MAQ-BOD-CO-002"
        assert (segundo.categoria, segundo.ubicacion, segundo.grupo, segundo.tipo) == ("Maquinaria", "Bodega", "002", "CO")


def test_siguiente_despues_del_205_es_206(client, app, admin):
    with app.app_context():
        db.session.add(ArticuloInventario(
            codigo="ZF-MAQ-CO-205", nombre="Mesa", categoria="Maquinaria", descripcion="Mesa", stock=1, stock_maximo=1,
            unidad="unidades", ubicacion="Bodega", imagen_url="x.png",
        ))
        db.session.commit()
    datos = client.get("/api/inventario/siguiente-codigo?categoria=MAQ&ubicacion=BOD&tipo=CO").get_json()
    assert datos["codigo"] == "ZF-MAQ-CO-206"


def test_no_deja_saltarse_el_consecutivo_a_mano(client, admin):
    assert _crear(client, codigo="ZF-MAQ-CO-001").status_code == 201
    respuesta = _crear(client, codigo="ZF-MAQ-CO-300")
    assert respuesta.status_code == 400
    assert "ZF-MAQ-CO-002" in respuesta.get_json()["error"]
    # La mercancía de clientes usa otros códigos: no aplica el consecutivo.
    assert _crear(client, codigo="SER-2026-09-29-BOM").status_code == 201


def test_el_codigo_automatico_editado_tampoco_se_salta_el_consecutivo(client, app, admin):
    datos = {"sigla_categoria": "HE", "sigla_ubicacion": "BOD", "tipo": "CO"}
    assert _crear(client, **datos, codigo="ZF-HE-CO-900", codigo_sugerido="ZF-HE-CO-001").status_code == 400
    assert _crear(client, **datos, codigo="ZF-HE-CO-001", codigo_sugerido="ZF-HE-CO-001").status_code == 201
    with app.app_context():
        assert ArticuloInventario.query.filter_by(codigo="ZF-HE-CO-001").count() == 1


def test_no_reutiliza_el_codigo_de_un_articulo_eliminado(client, app, admin):
    datos = {"sigla_categoria": "OT", "sigla_ubicacion": "OP", "tipo": "CO"}
    creado = _crear(client, **datos).get_json()["articulo"]["id"]
    assert client.delete(f"/api/inventario/{creado}").status_code == 200
    siguiente = client.get("/api/inventario/siguiente-codigo?categoria=OT&ubicacion=OP&tipo=CO").get_json()
    assert siguiente["codigo"] == "ZF-OT-CO-002"


@pytest.mark.parametrize("datos", [
    {"sigla_categoria": "MAQ"},
    {"sigla_categoria": "XX", "sigla_ubicacion": "BOD", "tipo": "CO"},
    {"sigla_categoria": "MAQ", "sigla_ubicacion": "BOD", "tipo": "ZZ"},
])
def test_codigo_automatico_incompleto_o_invalido(client, admin, datos):
    assert _crear(client, **datos).status_code == 400


# --- Ingresar existencias con documento soporte --------------------------------

def _ingresar(client, id_articulo, archivo=None, cantidad="3", **datos):
    cuerpo = {"cantidad": cantidad, **datos}
    if archivo is not None:
        cuerpo["documento"] = archivo
    return client.post(f"/api/inventario/{id_articulo}/ingresar", data=cuerpo, content_type="multipart/form-data")


def test_ingresar_existencias_con_documento(client, app, admin, kit):
    respuesta = _ingresar(client, kit, (BytesIO(PDF), "Factura 123.pdf"), formulario="1384500", observaciones="Compra")
    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["articulo"]["stock"] == 5
    movimiento = datos["movimiento"]
    assert movimiento["documento_nombre"] == "Factura 123.pdf"
    assert movimiento["formulario"] == "1384500"

    descarga = client.get(movimiento["documento_url"])
    assert descarga.status_code == 200
    assert descarga.data == PDF
    assert descarga.mimetype == "application/pdf"
    assert "attachment" in descarga.headers["Content-Disposition"]

    # Aparece también en la trazabilidad del código.
    eventos = client.get("/api/inventario/trazabilidad/SER-2026-09-29").get_json()["eventos"]
    assert eventos[0]["documento_nombre"] == "Factura 123.pdf"


def test_ingreso_sin_documento_y_con_imagen(client, admin, kit, imagen_png):
    assert _ingresar(client, kit).get_json()["movimiento"]["documento_url"] is None
    con_imagen = _ingresar(client, kit, (BytesIO(imagen_png), "foto.png"))
    assert con_imagen.get_json()["movimiento"]["documento_nombre"] == "foto.png"


def test_documento_de_tipo_no_permitido_no_ingresa_nada(client, app, admin, kit):
    respuesta = _ingresar(client, kit, (BytesIO(b"MZ ejecutable"), "factura.pdf"))
    assert respuesta.status_code == 400
    assert "PDF" in respuesta.get_json()["error"]
    with app.app_context():
        assert db.session.get(ArticuloInventario, kit).stock == 2
        assert MovimientoInventario.query.count() == 0


def test_cantidad_invalida_en_formulario(client, admin, kit):
    assert _ingresar(client, kit, cantidad="0").status_code == 400
    assert _ingresar(client, kit, cantidad="dos").status_code == 400


def test_documento_requiere_permiso(client, app, creador_usuarios, iniciar_sesion, kit):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    # Un empleado puede ingresar con documento, pero no descargar los documentos.
    url = _ingresar(client, kit, (BytesIO(PDF), "f.pdf")).get_json()["movimiento"]["documento_url"]
    assert client.get(url).status_code == 403
    client.post("/api/logout")
    assert client.get(url).status_code == 401


def test_movimiento_sin_documento_404(client, admin, kit):
    id_movimiento = _ingresar(client, kit).get_json()["movimiento"]["id"]
    assert client.get(f"/api/inventario/movimientos/{id_movimiento}/documento").status_code == 404
