"""Tests de la operación de Sizfra en los movimientos (R3) y las salidas integradas (R4)."""

import pytest
from sqlalchemy import create_engine, inspect, text

from mi_app import create_app
from mi_app.extensions import db
from mi_app.models import ArticuloInventario, MovimientoInventario, SalidaIntegrada


@pytest.fixture()
def articulos(app):
    """Crea un banco y dos partes; devuelve sus ids."""
    datos = [
        ("ZF-MAQ-CO-001", "Banco hidráulico", 3),
        ("ZF-MAQ-CO-090", "Kit de accesorios", 5),
        ("ZF-MAQ-CO-091", "Arrancador neumático", 1),
    ]
    with app.app_context():
        ids = []
        for codigo, nombre, stock in datos:
            articulo = ArticuloInventario(
                codigo=codigo, nombre=nombre, categoria="Maquinaria", descripcion=nombre,
                stock=stock, stock_maximo=stock, unidad="unidades", ubicacion="Bodega",
                imagen_url="https://ejemplo.com/imagen.png",
            )
            db.session.add(articulo)
            db.session.flush()
            ids.append(articulo.id)
        db.session.commit()
        return ids


@pytest.fixture()
def sesion(creador_usuarios, iniciar_sesion):
    creador_usuarios("operario", nombre_completo="Operario Bodega")
    iniciar_sesion("operario")


def _stock(app, id_articulo):
    with app.app_context():
        return db.session.get(ArticuloInventario, id_articulo).stock


# --- R3: operación y formulario de Sizfra en ingresos y retiros -------------

def test_retiro_guarda_operacion_y_formulario(client, app, articulos, sesion):
    banco = articulos[0]
    respuesta = client.post(
        f"/api/inventario/{banco}/retirar",
        json={"cantidad": 1, "operacion_sizfra": "420", "formulario": "1383926"},
    )
    assert respuesta.status_code == 200
    movimiento = respuesta.get_json()["movimiento"]
    assert (movimiento["operacion_sizfra"], movimiento["formulario"]) == ("420", "1383926")
    assert _stock(app, banco) == 2


def test_ingreso_guarda_operacion_y_formulario(client, app, articulos, sesion):
    banco = articulos[0]
    client.post(f"/api/inventario/{banco}/retirar", json={"cantidad": 1})
    respuesta = client.post(
        f"/api/inventario/{banco}/ingresar",
        json={"cantidad": 1, "operacion_sizfra": "101", "formulario": "f-77"},
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["movimiento"]["formulario"] == "F-77"


def test_retiro_sin_datos_sizfra_sigue_funcionando(client, articulos, sesion):
    respuesta = client.post(f"/api/inventario/{articulos[0]}/retirar", json={"cantidad": 1})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["movimiento"]["operacion_sizfra"] is None


@pytest.mark.parametrize("datos", [
    {"operacion_sizfra": "cuatro"},
    {"operacion_sizfra": "1234567"},
    {"formulario": "form 1"},
])
def test_retiro_rechaza_datos_sizfra_invalidos(client, app, articulos, sesion, datos):
    respuesta = client.post(f"/api/inventario/{articulos[0]}/retirar", json={"cantidad": 1, **datos})
    assert respuesta.status_code == 400
    assert _stock(app, articulos[0]) == 3


# --- R4: salida con integración de partes -----------------------------------

def _salida(client, **datos):
    return client.post("/api/inventario/salidas-integradas", json=datos)


def test_salida_integrada_requiere_sesion(client, articulos):
    respuesta = _salida(client, componentes=[{"id": articulos[1], "cantidad": 1}], proceso="Reparación", referencia="X")
    assert respuesta.status_code == 401


def test_salida_integrada_descuenta_todo_en_un_registro(client, app, articulos, sesion):
    banco, kit, arrancador = articulos
    respuesta = _salida(
        client,
        principal={"id": banco, "cantidad": 1},
        componentes=[{"id": kit, "cantidad": 2}, {"id": arrancador, "cantidad": 1}],
        proceso="Reparación",
        operacion_sizfra="420",
        formulario="1383926",
        observaciones="Restauración del banco.",
    )
    assert respuesta.status_code == 201
    datos = respuesta.get_json()
    salida = datos["salida"]
    # Sin referencia escrita se usa el equipo principal.
    assert salida["referencia"] == "ZF-MAQ-CO-001 · Banco hidráulico"
    assert [(m["codigo_articulo"], m["rol"], m["cantidad"]) for m in salida["movimientos"]] == [
        ("ZF-MAQ-CO-001", "Principal", 1),
        ("ZF-MAQ-CO-090", "Integrado", 2),
        ("ZF-MAQ-CO-091", "Integrado", 1),
    ]
    assert all(m["tipo"] == "Retiro" and m["formulario"] == "1383926" for m in salida["movimientos"])
    assert datos["stocks"] == {str(banco): 2, str(kit): 3, str(arrancador): 0}
    assert salida["empleado"] == "Operario Bodega"

    # El historial muestra a qué salida pertenece cada parte.
    with app.app_context():
        parte = MovimientoInventario.query.filter_by(codigo_articulo="ZF-MAQ-CO-091").one()
        assert parte.to_dict()["referencia"] == "ZF-MAQ-CO-001 · Banco hidráulico"
        assert parte.to_dict()["proceso"] == "Reparación"


def test_salida_integrada_sin_equipo_principal(client, app, articulos, sesion):
    """Fabricación de un producto nuevo: solo salen partes, con una referencia escrita."""
    respuesta = _salida(
        client,
        componentes=[{"id": articulos[1], "cantidad": 1}],
        proceso="Fabricación",
        referencia="Banco nuevo ref. FAB-001",
    )
    assert respuesta.status_code == 201
    assert respuesta.get_json()["salida"]["referencia"] == "Banco nuevo ref. FAB-001"


def test_salida_integrada_sin_stock_no_descuenta_nada(client, app, articulos, sesion):
    banco, kit, arrancador = articulos
    respuesta = _salida(
        client,
        principal={"id": banco, "cantidad": 1},
        componentes=[{"id": kit, "cantidad": 1}, {"id": arrancador, "cantidad": 2}],
        proceso="Reparación",
    )
    assert respuesta.status_code == 409
    assert "ZF-MAQ-CO-091" in respuesta.get_json()["error"]
    assert [_stock(app, i) for i in articulos] == [3, 5, 1]
    with app.app_context():
        assert SalidaIntegrada.query.count() == 0
        assert MovimientoInventario.query.count() == 0


@pytest.mark.parametrize("datos, mensaje", [
    ({"componentes": []}, "al menos una parte"),
    ({"proceso": "Pintura"}, "proceso"),
    ({"principal": None, "referencia": ""}, "referencia"),
    ({"componentes": [{"id": "1", "cantidad": 1}]}, "artículo"),
    ({"componentes": [{"id": 2, "cantidad": 0}]}, "cantidad"),
])
def test_salida_integrada_validaciones(client, app, articulos, sesion, datos, mensaje):
    base = {
        "principal": {"id": articulos[0], "cantidad": 1},
        "componentes": [{"id": articulos[1], "cantidad": 1}],
        "proceso": "Reparación",
    }
    respuesta = _salida(client, **{**base, **datos})
    assert respuesta.status_code == 400
    assert mensaje in respuesta.get_json()["error"]
    assert _stock(app, articulos[1]) == 5


def test_salida_integrada_rechaza_articulo_repetido(client, articulos, sesion):
    respuesta = _salida(
        client,
        principal={"id": articulos[0], "cantidad": 1},
        componentes=[{"id": articulos[0], "cantidad": 1}],
        proceso="Reparación",
    )
    assert respuesta.status_code == 400


def test_salida_integrada_articulo_inexistente_404(client, articulos, sesion):
    respuesta = _salida(client, componentes=[{"id": 9999, "cantidad": 1}], proceso="Reparación", referencia="X")
    assert respuesta.status_code == 404


def test_obtener_salida_integrada(client, articulos, sesion):
    creada = _salida(
        client,
        componentes=[{"id": articulos[1], "cantidad": 1}],
        proceso="Mantenimiento",
        referencia="Banco ref. 1",
    ).get_json()["salida"]
    respuesta = client.get(f"/api/inventario/salidas-integradas/{creada['id']}")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["salida"]["movimientos"][0]["rol"] == "Integrado"
    assert client.get("/api/inventario/salidas-integradas/9999").status_code == 404


def test_dashboard_tiene_boton_de_salida_integrada(client, articulos, sesion):
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="open-integrated-exit"' in html
    assert 'value="ZF-MAQ-CO-090 · Kit de accesorios"' in html


def test_migracion_agrega_columnas_sizfra_a_movimientos(tmp_path):
    url = f"sqlite:///{(tmp_path / 'vieja.sqlite3').as_posix()}"
    motor = create_engine(url)
    with motor.begin() as conexion:
        conexion.execute(text(
            "CREATE TABLE movimientos_inventario (id INTEGER PRIMARY KEY, empleado VARCHAR(120) NOT NULL, "
            "usuario VARCHAR(80) NOT NULL, articulo VARCHAR(120) NOT NULL, codigo_articulo VARCHAR(24) NOT NULL, "
            "categoria VARCHAR(60) NOT NULL, tipo VARCHAR(16) NOT NULL, cantidad INTEGER NOT NULL, "
            "unidad VARCHAR(24) NOT NULL, fecha_hora DATETIME NOT NULL)"
        ))
    motor.dispose()

    app = create_app({"TESTING": True, "SECRET_KEY": "x", "SQLALCHEMY_DATABASE_URI": url})
    with app.app_context():
        columnas = {c["name"] for c in inspect(db.engine).get_columns("movimientos_inventario")}
        assert {"operacion_sizfra", "formulario", "id_salida", "rol"} <= columnas
        assert "salidas_integradas" in inspect(db.engine).get_table_names()
        db.session.remove()
        db.engine.dispose()
