"""Código consecutivo editable y hasta 3 imágenes por artículo."""

import os
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from mi_app.extensions import db
from mi_app.models import ArticuloInventario


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")


def _crear(client, **extra):
    datos = {
        "nombre": "Bomba", "descripcion": "Bomba.", "stock": "1",
        "sigla_categoria": "MAQ", "sigla_ubicacion": "BOD", "tipo": "CO",
    }
    datos.update(extra)
    return client.post("/api/inventario/", data=datos, content_type="multipart/form-data")


def _articulo(app, id_articulo=None):
    with app.app_context():
        articulo = (
            db.session.get(ArticuloInventario, id_articulo) if id_articulo
            else ArticuloInventario.query.order_by(ArticuloInventario.id.desc()).first()
        )
        db.session.expunge(articulo)
        return articulo


def _png(imagen_png):
    return BytesIO(imagen_png), "foto.png"


def _ruta(app, url):
    return Path(app.static_folder) / "images" / "inventory" / Path(url).name


def test_codigo_vacio_es_automatico_y_sube_de_uno_en_uno(client, app, admin):
    assert _crear(client).status_code == 201
    assert _articulo(app).codigo == "ZF-MAQ-CO-001"
    assert _articulo(app).codigo_interno == "MAQ-BOD-CO-001"
    assert _crear(client).status_code == 201
    assert _articulo(app).codigo == "ZF-MAQ-CO-002"


def test_codigo_editado_se_respeta(client, app, admin):
    respuesta = _crear(
        client, codigo="zf-maq-co-001", codigo_sugerido="ZF-MAQ-CO-002",
        codigo_interno="MAQ-X", codigo_interno_sugerido="MAQ-BOD-CO-002",
    )
    assert respuesta.status_code == 201
    assert (_articulo(app).codigo, _articulo(app).codigo_interno) == ("ZF-MAQ-CO-001", "MAQ-X")


def test_codigo_sugerido_viejo_toma_el_numero_actual(client, app, admin):
    _crear(client)
    respuesta = _crear(
        client, codigo="ZF-MAQ-CO-001", codigo_sugerido="ZF-MAQ-CO-001",
        codigo_interno="MAQ-BOD-CO-001", codigo_interno_sugerido="MAQ-BOD-CO-001",
    )
    assert respuesta.status_code == 201
    assert (_articulo(app).codigo, _articulo(app).codigo_interno) == ("ZF-MAQ-CO-002", "MAQ-BOD-CO-002")


@pytest.mark.parametrize("codigo, estado", [("ZF MAQ", 400), ("ZF-MAQ-CO-050", 400)])
def test_codigo_editado_invalido_o_con_salto(client, admin, codigo, estado):
    assert _crear(client, codigo=codigo, codigo_sugerido="ZF-MAQ-CO-001").status_code == estado


def test_codigo_editado_repetido(client, admin):
    _crear(client)
    assert _crear(client, codigo="ZF-MAQ-CO-001", codigo_sugerido="ZF-MAQ-CO-002").status_code == 409


def test_sin_imagenes_usa_la_de_la_bodega(client, app, admin):
    assert _crear(client).status_code == 201
    articulo = _articulo(app)
    assert articulo.imagen_url.endswith("workshop-bg.jpg")
    assert articulo.imagenes == []


def test_guarda_tres_imagenes(client, app, admin, imagen_png):
    assert _crear(
        client, imagen=_png(imagen_png), imagen_2=_png(imagen_png), imagen_3=_png(imagen_png),
    ).status_code == 201
    imagenes = _articulo(app).imagenes
    assert len(set(imagenes)) == 3
    assert all(_ruta(app, url).is_file() for url in imagenes)


def test_una_sola_imagen_en_cualquier_casilla_queda_principal(client, app, admin, imagen_png):
    assert _crear(client, imagen_3=_png(imagen_png)).status_code == 201
    articulo = _articulo(app)
    assert len(articulo.imagenes) == 1
    assert articulo.imagen_url == articulo.imagenes[0]
    assert articulo.imagen_url_3 is None


def _ruido(lado):
    bufer = BytesIO()
    Image.frombytes("RGB", (lado, lado), os.urandom(lado * lado * 3)).save(bufer, format="PNG")
    bufer.seek(0)
    return bufer, "grande.png"


def test_acepta_tres_imagenes_que_juntas_pasan_de_5_mb(client, app, admin):
    assert _crear(client, imagen=_ruido(1100), imagen_2=_ruido(1100), imagen_3=_ruido(1100)).status_code == 201
    assert len(_articulo(app).imagenes) == 3


def test_rechaza_imagen_de_mas_de_5_mb_sin_dejar_archivos(client, app, admin, imagen_png):
    respuesta = _crear(client, imagen=_png(imagen_png), imagen_2=_ruido(1500))
    assert respuesta.status_code == 400
    assert not list((Path(app.static_folder) / "images" / "inventory").iterdir())


def _editar(client, id_articulo, **extra):
    datos = {"nombre": "Bomba", "descripcion": "Bomba.", "categoria": "Maquinaria"}
    datos.update(extra)
    return client.put(f"/api/inventario/{id_articulo}", data=datos, content_type="multipart/form-data")


def test_editar_reemplaza_quita_y_reacomoda(client, app, admin, imagen_png):
    _crear(client, imagen=_png(imagen_png), imagen_2=_png(imagen_png), imagen_3=_png(imagen_png))
    articulo = _articulo(app)
    primera, segunda, tercera = articulo.imagenes

    assert _editar(client, articulo.id, quitar_imagen_1="1", imagen_2=_png(imagen_png)).status_code == 200
    despues = _articulo(app, articulo.id).imagenes
    assert len(despues) == 2 and despues[1] == tercera and despues[0] not in (primera, segunda)
    assert not _ruta(app, primera).exists() and not _ruta(app, segunda).exists()
    assert _ruta(app, tercera).exists()


def test_editar_agrega_y_quitar_todas_vuelve_a_la_bodega(client, app, admin, imagen_png):
    _crear(client)
    articulo = _articulo(app)
    assert _editar(client, articulo.id, imagen_2=_png(imagen_png)).status_code == 200
    actual = _articulo(app, articulo.id)
    assert len(actual.imagenes) == 1

    assert _editar(client, articulo.id, quitar_imagen_1="1").status_code == 200
    actual = _articulo(app, articulo.id)
    assert actual.imagenes == [] and actual.imagen_url.endswith("workshop-bg.jpg")


def test_borrar_articulo_borra_sus_imagenes(client, app, admin, imagen_png):
    _crear(client, stock="0", imagen=_png(imagen_png), imagen_2=_png(imagen_png))
    articulo = _articulo(app)
    assert client.delete(f"/api/inventario/{articulo.id}").get_json()["baja"] is False
    assert not list((Path(app.static_folder) / "images" / "inventory").iterdir())


def test_dashboard_entrega_las_imagenes(client, app, admin, imagen_png):
    _crear(client, imagen=_png(imagen_png), imagen_2=_png(imagen_png))
    html = client.get("/dashboard").get_data(as_text=True)
    assert "data-images='[\"/static/images/inventory/" in html
