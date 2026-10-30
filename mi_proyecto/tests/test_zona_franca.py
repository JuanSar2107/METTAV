"""Tests de los campos de zona franca y la importación desde Excel."""

from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, inspect, text

from mi_app import create_app
from mi_app.extensions import db
from mi_app.models import ArticuloInventario, Categoria, MovimientoInventario
from mi_app.zona_franca import leer_valor_fob


def _excel(filas, encabezados=None, titulo="Inventario Equipos"):
    """Arma un .xlsx en memoria con el formato del Excel de METTAV."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = titulo
    hoja.append(encabezados or [
        "Código interno", "Codigo ZF", "Categoria (EQ/MAQ/EL/MO/HE/OT)",
        "Ubicación (ADM/BOD/COM/OP)", "Tipo (PR/CO/A)", "Consecutivo (auto)", "Descripción", "Marca",
    ])
    for fila in filas:
        hoja.append(fila)
    bufer = BytesIO()
    libro.save(bufer)
    bufer.seek(0)
    return bufer


def _importar(client, archivo, nombre="inventario.xlsx"):
    return client.post(
        "/api/inventario/importar",
        data={"archivo": (archivo, nombre)},
        content_type="multipart/form-data",
    )


@pytest.fixture()
def admin(creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")


@pytest.mark.parametrize("texto, esperado", [
    ("1200", Decimal("1200.00")),
    ("1.200,50", Decimal("1200.50")),
    ("1,200.50", Decimal("1200.50")),
    ("1200,5", Decimal("1200.50")),
    ("1.200", Decimal("1200.00")),
    ("USD 99.9", Decimal("99.90")),
    ("", None),
])
def test_leer_valor_fob(texto, esperado):
    assert leer_valor_fob(texto) == esperado


def test_leer_valor_fob_invalido():
    with pytest.raises(ValueError):
        leer_valor_fob("mil")


def test_crear_articulo_con_campos_zona_franca(client, app, admin, imagen_png):
    respuesta = client.post(
        "/api/inventario/",
        data={
            "nombre": "Bomba de aceite",
            "descripcion": "Bomba de aceite para reparación.",
            "stock": "1",
            "codigo": "zf-maq-co-090",
            "codigo_interno": "MAQ-BOD-CO-090",
            "grupo": "4",
            "marca": "N/A",
            "subpartida": "8413.30.10.00",
            "valor_fob_usd": "1.200,00",
            "procedencia": "nacional",
            "estado": "Para reparación",
            "imagen": (BytesIO(imagen_png), "imagen.png"),
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 201
    with app.app_context():
        articulo = ArticuloInventario.query.filter_by(codigo="ZF-MAQ-CO-090").one()
        assert articulo.codigo_interno == "MAQ-BOD-CO-090"
        assert articulo.grupo == "004"
        assert articulo.marca is None
        assert articulo.subpartida == "8413.30.10.00"
        assert articulo.valor_fob_usd == Decimal("1200.00")
        assert articulo.procedencia == "Nacional"
        assert articulo.estado == "Para reparación"


@pytest.mark.parametrize("campo, valor", [
    ("subpartida", "84A3"),
    ("grupo", "009"),
    ("procedencia", "Marte"),
    ("valor_fob_usd", "-5"),
    ("codigo", "ZF MAQ 1"),
])
def test_crear_articulo_rechaza_campos_invalidos(client, admin, imagen_png, campo, valor):
    respuesta = client.post(
        "/api/inventario/",
        data={
            "nombre": "Bomba",
            "descripcion": "Bomba.",
            "stock": "1",
            campo: valor,
            "imagen": (BytesIO(imagen_png), "imagen.png"),
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 400


def test_crear_articulo_codigo_zf_repetido_409(client, admin, imagen_png):
    datos = lambda: {  # noqa: E731
        "nombre": "Bomba",
        "descripcion": "Bomba.",
        "stock": "1",
        "codigo": "ZF-MAQ-CO-001",
        "imagen": (BytesIO(imagen_png), "imagen.png"),
    }
    assert client.post("/api/inventario/", data=datos(), content_type="multipart/form-data").status_code == 201
    respuesta = client.post("/api/inventario/", data=datos(), content_type="multipart/form-data")
    assert respuesta.status_code == 409


def test_importar_requiere_admin(client, creador_usuarios, iniciar_sesion):
    assert _importar(client, _excel([])).status_code == 401
    creador_usuarios("normal")
    iniciar_sesion("normal")
    assert _importar(client, _excel([])).status_code == 403


def test_importar_excel_crea_articulos(client, app, admin):
    archivo = _excel([
        ["MAQ-BOD-CO-001", "ZF-MAQ-CO-001", "MAQ", "BOD", "CO", 1, "Banco hidraulico de componentes", "N/A"],
        ["OT-OP-CO-001", "ZF-OT-CO-001", "OT", "OP", "CO", 1, "camillas con ruedas", None],
        ["MO-APT-CO-002", "ZF-MO-CO-002", "MO", "APT", "CO", 2, "sillones color gris (2 und)", None],
        # Código ZF sin valor (fórmula sin calcular): se arma con categoría, tipo y consecutivo.
        ["EQ-ADM-CO-007", None, "EQ", "ADM", "CO", 7, "Impresora multifuncional negra", "Epson"],
        [None, None, None, None, None, None, None, None],  # fila separadora
    ])
    respuesta = _importar(client, archivo)
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"creados": 4, "actualizados": 0, "errores": [], "avisos": []}

    with app.app_context():
        banco = ArticuloInventario.query.filter_by(codigo="ZF-MAQ-CO-001").one()
        assert banco.codigo_interno == "MAQ-BOD-CO-001"
        assert banco.grupo == "002"
        assert banco.categoria == "Maquinaria"
        assert banco.ubicacion == "Bodega"
        assert banco.marca is None
        assert banco.stock == banco.stock_maximo == 1
        assert ArticuloInventario.query.filter_by(codigo="ZF-OT-CO-001").one().grupo == "003"
        sillones = ArticuloInventario.query.filter_by(codigo="ZF-MO-CO-002").one()
        assert (sillones.grupo, sillones.stock) == ("001", 2)
        impresora = ArticuloInventario.query.filter_by(codigo="ZF-EQ-CO-007").one()
        assert impresora.marca == "Epson"
        assert Categoria.query.filter_by(nombre="Maquinaria").one()
        # Cada artículo nuevo deja su ingreso en el historial.
        assert MovimientoInventario.query.filter_by(tipo="Ingreso").count() == 4


def test_importar_de_nuevo_actualiza_sin_tocar_stock(client, app, admin):
    fila = ["MAQ-BOD-CO-001", "ZF-MAQ-CO-001", "MAQ", "BOD", "CO", 1, "Banco hidraulico", "N/A"]
    _importar(client, _excel([fila]))
    with app.app_context():
        articulo = ArticuloInventario.query.filter_by(codigo="ZF-MAQ-CO-001").one()
        articulo.stock = 0
        db.session.commit()

    fila[6] = "Banco hidráulico de componentes"
    respuesta = _importar(client, _excel([fila]))
    assert respuesta.get_json() == {"creados": 0, "actualizados": 1, "errores": [], "avisos": []}
    with app.app_context():
        articulo = ArticuloInventario.query.filter_by(codigo="ZF-MAQ-CO-001").one()
        assert articulo.descripcion == "Banco hidráulico de componentes"
        assert articulo.stock == 0


def test_importar_reporta_filas_con_error(client, app, admin):
    archivo = _excel(
        [
            ["ZF-MAQ-CO-001", "Banco", "8413.30.10.00", "1200"],
            ["ZF-EL-CO-001", "TV", "", ""],
            ["ZF-EL-CO-001", "Nevera con el mismo código", "", ""],
            ["", "Sin código", "", ""],
            ["ZF-MAQ-CO-002", "Subpartida mala", "84-13", ""],
        ],
        encabezados=["Código ZF", "Descripción", "Subpartida arancelaria", "Valor FOB"],
    )
    datos = _importar(client, archivo).get_json()
    assert datos["creados"] == 1
    # Las dos filas con el código repetido quedan fuera, no solo la segunda.
    assert [e["fila"] for e in datos["errores"]] == [3, 4, 5, 6]
    with app.app_context():
        articulo = ArticuloInventario.query.filter_by(codigo="ZF-MAQ-CO-001").one()
        assert articulo.valor_fob_usd == Decimal("1200.00")
        assert ArticuloInventario.query.filter_by(codigo="ZF-EL-CO-001").first() is None


def test_importar_prefiere_valor_usd_sobre_valor_fob_en_pesos(client, app, admin):
    """En el Excel de METTAV 'Valor FOB' está en pesos y 'valor USD' en dólares."""
    archivo = _excel(
        [["ZF-MAQ-CO-001", "Banco", 8413301000, 80, 255000]],
        encabezados=["Codigo ZF ", "Descripción", "SUB PARTIDA", "valor USD", "Valor FOB"],
    )
    assert _importar(client, archivo).get_json()["creados"] == 1
    with app.app_context():
        articulo = ArticuloInventario.query.filter_by(codigo="ZF-MAQ-CO-001").one()
        assert articulo.valor_fob_usd == Decimal("80.00")
        assert articulo.subpartida == "8413301000"


def test_importar_archivo_invalido(client, admin):
    assert _importar(client, BytesIO(b"no es excel"), "datos.csv").status_code == 400
    assert _importar(client, BytesIO(b"no es excel")).status_code == 400
    sin_encabezados = _excel([["a", "b"]], encabezados=["Nombre", "Precio"])
    respuesta = _importar(client, sin_encabezados)
    assert respuesta.status_code == 400
    assert "encabezados" in respuesta.get_json()["error"]


def test_dashboard_muestra_campos_zona_franca(client, app, admin):
    _importar(client, _excel([
        ["MAQ-BOD-CO-001", "ZF-MAQ-CO-001", "MAQ", "BOD", "CO", 1, "Banco hidraulico", "N/A"],
    ]))
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'data-internal-code="MAQ-BOD-CO-001"' in html
    assert 'data-group-name="Equipos de bodega"' in html
    assert "Importar Excel" in html


def test_migracion_agrega_columnas_a_base_vieja(tmp_path):
    """Una base creada antes de estos campos recibe las columnas nuevas al arrancar."""
    url = f"sqlite:///{(tmp_path / 'vieja.sqlite3').as_posix()}"
    motor = create_engine(url)
    with motor.begin() as conexion:
        conexion.execute(text(
            "CREATE TABLE articulos_inventario (id INTEGER PRIMARY KEY, codigo VARCHAR(24) UNIQUE NOT NULL, "
            "nombre VARCHAR(120) NOT NULL, categoria VARCHAR(60) NOT NULL, descripcion TEXT NOT NULL, "
            "stock INTEGER NOT NULL, stock_maximo INTEGER NOT NULL DEFAULT 0, unidad VARCHAR(24) NOT NULL, "
            "ubicacion VARCHAR(80) NOT NULL, imagen_url VARCHAR(500) NOT NULL)"
        ))
    motor.dispose()

    app = create_app({"TESTING": True, "SECRET_KEY": "x", "SQLALCHEMY_DATABASE_URI": url})
    with app.app_context():
        columnas = {c["name"] for c in inspect(db.engine).get_columns("articulos_inventario")}
        assert {"codigo_interno", "grupo", "subpartida", "valor_fob_usd", "procedencia"} <= columnas
        db.session.remove()
        db.engine.dispose()
