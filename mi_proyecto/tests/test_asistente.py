"""Tests del asistente con IA. Gemini se simula: nunca se llama a la API real."""

import io
import json
import urllib.error

import pytest

from mi_app import gemini


@pytest.fixture()
def con_clave(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")


@pytest.fixture()
def gemini_falso(monkeypatch, con_clave):
    """Reemplaza la llamada a Gemini y guarda lo que recibió."""
    llamadas = []

    def _consultar(instrucciones, mensajes):
        llamadas.append({"instrucciones": instrucciones, "mensajes": mensajes})
        return "Respuesta simulada"

    monkeypatch.setattr(gemini, "consultar_gemini", _consultar)
    return llamadas


def test_asistente_requiere_sesion(client):
    respuesta = client.post("/api/asistente/", json={"pregunta": "Hola"})
    assert respuesta.status_code == 401


def test_asistente_sin_clave_responde_503(client, monkeypatch, creador_usuarios, iniciar_sesion):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    creador_usuarios("ana")
    iniciar_sesion("ana")

    respuesta = client.post("/api/asistente/", json={"pregunta": "Hola"})
    assert respuesta.status_code == 503
    assert "GEMINI_API_KEY" in respuesta.get_json()["error"]


def test_asistente_rechaza_pregunta_vacia(client, con_clave, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")

    respuesta = client.post("/api/asistente/", json={"pregunta": "   "})
    assert respuesta.status_code == 400


def test_asistente_responde_con_contexto_del_inventario(client, gemini_falso, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    client.get("/dashboard")  # siembra el inventario de ejemplo

    respuesta = client.post(
        "/api/asistente/",
        json={
            "pregunta": "¿Qué tiene stock bajo?",
            "historial": [
                {"rol": "asistente", "texto": "Saludo inicial que se descarta"},
                {"rol": "usuario", "texto": "Hola"},
                {"rol": "asistente", "texto": "¡Hola!"},
                {"rol": "sistema", "texto": "ignorado"},
            ],
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"respuesta": "Respuesta simulada"}
    llamada = gemini_falso[0]
    assert "Guantes de protección" in llamada["instrucciones"]
    assert "ÚLTIMOS MOVIMIENTOS" not in llamada["instrucciones"]
    assert [m["rol"] for m in llamada["mensajes"]] == ["usuario", "asistente", "usuario"]
    assert llamada["mensajes"][-1]["texto"] == "¿Qué tiene stock bajo?"


def test_asistente_incluye_movimientos_para_admin(client, gemini_falso, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    iniciar_sesion("jefe")

    respuesta = client.post("/api/asistente/", json={"pregunta": "Resumen"})
    assert respuesta.status_code == 200
    assert "ÚLTIMOS MOVIMIENTOS" in gemini_falso[0]["instrucciones"]


@pytest.fixture()
def operacion_zona_franca(app):
    """Un banco con datos de Sizfra, una parte, una salida integrada y una remisión."""
    from datetime import date
    from decimal import Decimal

    from mi_app.extensions import db
    from mi_app.models import ArticuloInventario

    with app.app_context():
        articulos = [
            ArticuloInventario(
                codigo="ZF-MAQ-CO-001", codigo_interno="MAQ-BOD-CO-001", nombre="Banco hidráulico",
                categoria="Maquinaria", descripcion="Banco", grupo="002", stock=2, stock_maximo=2,
                unidad="unidades", ubicacion="Bodega", imagen_url="x.png", subpartida="8413301000",
                valor_fob_usd=Decimal("80.00"), serial="B-77", responsable="Operativos",
                fecha_ingreso=date(2026, 5, 8),
            ),
            ArticuloInventario(
                codigo="ZF-MAQ-CO-090", nombre="Kit de accesorios", categoria="Maquinaria", descripcion="Kit",
                grupo="002", stock=3, stock_maximo=3, unidad="unidades", ubicacion="Bodega", imagen_url="x.png",
            ),
            ArticuloInventario(
                codigo="SER-2026-BOM", nombre="Bomba de aceite", categoria="Maquinaria", descripcion="Bomba",
                grupo="004", stock=1, stock_maximo=1, unidad="unidades", ubicacion="Bodega", imagen_url="x.png",
                cliente="MOTORKAM", tipo_servicio="Reparación", estado_servicio="En servicio",
            ),
        ]
        db.session.add_all(articulos)
        db.session.commit()
        return [a.id for a in articulos]


def _registrar_operaciones(client, ids):
    banco, kit, bomba = ids
    client.post("/api/inventario/salidas-integradas", json={
        "principal": {"id": banco, "cantidad": 1},
        "componentes": [{"id": kit, "cantidad": 2}],
        "proceso": "Reparación",
        "formulario": "1383926",
    })
    client.post("/api/remisiones", json={
        "cliente_nombre": "MOTORKAM COMPANY S.A.S", "cliente_nit": "900.059.427-0",
        "lineas": [{"id": bomba, "cantidad": 1, "estado_servicio": "Entregado"}],
    })


def test_asistente_admin_conoce_zona_franca_salidas_y_remisiones(
    client, gemini_falso, creador_usuarios, iniciar_sesion, operacion_zona_franca
):
    creador_usuarios("jefe", es_admin=True, nombre_completo="Jefa de Bodega")
    iniciar_sesion("jefe")
    _registrar_operaciones(client, operacion_zona_franca)

    client.post("/api/asistente/", json={"pregunta": "¿Qué partes se integraron al banco?"})
    contexto = gemini_falso[0]["instrucciones"]
    # Conceptos de zona franca en las instrucciones.
    assert "Sizfra" in contexto and "004 mercancía de clientes" in contexto
    # Datos del artículo.
    assert "ZF-MAQ-CO-001 | Banco hidráulico | grupo 002" in contexto
    assert "interno MAQ-BOD-CO-001" in contexto
    assert "FOB USD 80.00" in contexto
    assert "serial B-77" in contexto
    # Salida integrada con su equipo y su parte.
    assert "Salida #1" in contexto
    assert "equipo: ZF-MAQ-CO-001 · Banco hidráulico" in contexto
    assert "parte: 2 unidades Kit de accesorios (ZF-MAQ-CO-090)" in contexto
    # Remisión y estado del servicio.
    assert "REM-0001" in contexto and "cliente MOTORKAM COMPANY S.A.S" in contexto
    assert "estado del servicio Entregado" in contexto
    # Movimientos con datos de Sizfra y auditoría.
    assert "formulario 1383926" in contexto
    assert "origen Remisión" in contexto
    assert "RESUMEN POR GRUPO DE SIZFRA" in contexto
    assert "REGISTROS DE AUDITORÍA" in contexto


def test_asistente_empleado_no_recibe_historial_ni_remisiones(
    client, gemini_falso, creador_usuarios, iniciar_sesion, operacion_zona_franca
):
    creador_usuarios("jefe", es_admin=True)
    iniciar_sesion("jefe")
    _registrar_operaciones(client, operacion_zona_franca)
    client.post("/api/logout")

    creador_usuarios("ana")
    iniciar_sesion("ana")
    client.post("/api/asistente/", json={"pregunta": "¿Qué se le entregó a MOTORKAM?"})
    contexto = gemini_falso[0]["instrucciones"]
    # El inventario sí (como en el panel), con su estado del servicio...
    assert "SER-2026-BOM" in contexto
    assert "estado del servicio Entregado" in contexto
    # ...pero nada del historial, las salidas, las remisiones ni la auditoría.
    for seccion in ("MOVIMIENTOS", "SALIDAS INTEGRADAS", "REMISIONES DE SALIDA", "AUDITORÍA", "cliente MOTORKAM COMPANY"):
        assert seccion not in contexto
    assert "son de administradores" in contexto


def test_asistente_avisa_cuando_el_inventario_supera_el_limite(
    client, app, gemini_falso, creador_usuarios, iniciar_sesion, monkeypatch
):
    from mi_app.extensions import db
    from mi_app.models import ArticuloInventario
    from mi_app.routes import assistant

    monkeypatch.setattr(assistant, "_MAX_ARTICULOS", 2)
    with app.app_context():
        db.session.add_all(
            ArticuloInventario(
                codigo=f"ZF-OT-CO-{i:03d}", nombre=f"Ítem {i}", categoria="Otros", descripcion="x",
                stock=1, stock_maximo=1, unidad="unidades", ubicacion="Bodega", imagen_url="x.png",
            )
            for i in range(3)
        )
        db.session.commit()
    creador_usuarios("ana")
    iniciar_sesion("ana")
    client.post("/api/asistente/", json={"pregunta": "¿Cuántos ítems hay?"})
    contexto = gemini_falso[0]["instrucciones"]
    assert "3 artículos, se muestran los primeros 2" in contexto
    assert "ZF-OT-CO-002" not in contexto


def test_asistente_error_de_gemini_responde_502(client, con_clave, monkeypatch, creador_usuarios, iniciar_sesion):
    def _falla(*_args):
        raise gemini.GeminiError("La clave GEMINI_API_KEY no es válida.")

    monkeypatch.setattr(gemini, "consultar_gemini", _falla)
    creador_usuarios("ana")
    iniciar_sesion("ana")

    respuesta = client.post("/api/asistente/", json={"pregunta": "Hola"})
    assert respuesta.status_code == 502
    assert respuesta.get_json()["error"] == "La clave GEMINI_API_KEY no es válida."


class _RespuestaFalsa(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_consultar_gemini_arma_peticion_y_lee_texto(monkeypatch, con_clave):
    enviadas = []

    def _urlopen(peticion, timeout):
        enviadas.append(peticion)
        cuerpo = {"candidates": [{"content": {"parts": [{"text": "Hay 5 pares."}]}}]}
        return _RespuestaFalsa(json.dumps(cuerpo).encode("utf-8"))

    monkeypatch.setattr(gemini.urllib.request, "urlopen", _urlopen)
    texto = gemini.consultar_gemini(
        "instrucciones",
        [{"rol": "usuario", "texto": "Hola"}, {"rol": "asistente", "texto": "Hey"}],
    )

    assert texto == "Hay 5 pares."
    peticion = enviadas[0]
    assert peticion.get_header("X-goog-api-key") == "clave-de-prueba"
    assert "gemini-3.5-flash:generateContent" in peticion.full_url
    cuerpo = json.loads(peticion.data)
    assert [c["role"] for c in cuerpo["contents"]] == ["user", "model"]


def test_consultar_gemini_traduce_clave_invalida(monkeypatch, con_clave):
    def _urlopen(peticion, timeout):
        detalle = json.dumps({"error": {"message": "API key not valid. Please pass a valid API key."}})
        raise urllib.error.HTTPError(peticion.full_url, 400, "Bad Request", {}, io.BytesIO(detalle.encode()))

    monkeypatch.setattr(gemini.urllib.request, "urlopen", _urlopen)
    with pytest.raises(gemini.GeminiError, match="no es válida"):
        gemini.consultar_gemini("x", [{"rol": "usuario", "texto": "Hola"}])
