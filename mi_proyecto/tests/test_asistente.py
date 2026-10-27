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
