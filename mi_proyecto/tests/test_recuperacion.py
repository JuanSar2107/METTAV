"""Tests de la recuperación de contraseña por correo."""

import re
import time

import pytest

from mi_app import correo, totp
from mi_app.extensions import db
from mi_app.models import TokenRecuperacion, Usuario


@pytest.fixture()
def buzon(monkeypatch):
    """Simula el servidor SMTP: guarda los correos en una lista."""
    enviados = []
    monkeypatch.setattr(correo, "configurado", lambda: True)
    monkeypatch.setattr(correo, "enviar", lambda destino, asunto, texto: enviados.append((destino, asunto, texto)))
    return enviados


def _enlace(buzon):
    return re.search(r"http://\S+/restablecer/(\S+)", buzon[-1][2])


def _pedir(client, identificador):
    return client.post("/api/recuperar", json={"identificador": identificador})


def test_pedir_enlace_envia_correo_al_correo_registrado(client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    respuesta = _pedir(client, "ana")
    assert respuesta.status_code == 200
    assert len(buzon) == 1
    destino, asunto, texto = buzon[0]
    assert destino == "ana@correo.com" and "contraseña" in asunto.lower()
    assert _enlace(buzon) is not None


def test_tambien_se_puede_pedir_con_el_correo(client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    assert _pedir(client, "ANA@correo.com").status_code == 200
    assert len(buzon) == 1


def test_la_respuesta_es_la_misma_exista_o_no_la_cuenta(client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    creador_usuarios("sin_correo")
    respuestas = [_pedir(client, x) for x in ("ana", "no-existe", "sin_correo")]
    assert {r.status_code for r in respuestas} == {200}
    assert len({r.get_data() for r in respuestas}) == 1
    assert len(buzon) == 1  # solo la cuenta con correo recibió algo


def test_el_token_se_guarda_solo_como_hash(app, client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    _pedir(client, "ana")
    token = _enlace(buzon).group(1)
    with app.app_context():
        guardado = TokenRecuperacion.query.one()
        assert token not in guardado.hash_token and len(guardado.hash_token) == 64


def test_restablecer_cambia_la_contrasena_y_cierra_sesiones(app, client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    abierta = app.test_client()
    abierta.post("/api/login", json={"usuario": "ana", "contrasena": "clave123"})
    assert abierta.get("/api/usuarios/me").status_code == 200

    _pedir(client, "ana")
    token = _enlace(buzon).group(1)
    assert "Contraseña nueva" in client.get(f"/restablecer/{token}").get_data(as_text=True)

    respuesta = client.post("/api/restablecer", json={"token": token, "contrasena": "elegida-por-correo-9"})
    assert respuesta.status_code == 200
    assert abierta.get("/api/usuarios/me").status_code == 401  # las sesiones viejas se cerraron
    assert client.post("/api/login", json={"usuario": "ana", "contrasena": "clave123"}).status_code == 401
    assert client.post("/api/login", json={"usuario": "ana", "contrasena": "elegida-por-correo-9"}).status_code == 200
    assert "cambiada" in buzon[-1][1]  # aviso de que se cambió


def test_el_enlace_solo_sirve_una_vez(client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    _pedir(client, "ana")
    token = _enlace(buzon).group(1)
    assert client.post("/api/restablecer", json={"token": token, "contrasena": "elegida-por-correo-9"}).status_code == 200
    segundo = client.post("/api/restablecer", json={"token": token, "contrasena": "otra-distinta-clave-7"})
    assert segundo.status_code == 400
    assert "no es válido" in client.get(f"/restablecer/{token}").get_data(as_text=True)


def test_un_enlace_nuevo_invalida_el_anterior(client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    _pedir(client, "ana")
    viejo = _enlace(buzon).group(1)
    _pedir(client, "ana")
    nuevo = _enlace(buzon).group(1)
    assert viejo != nuevo
    assert client.post("/api/restablecer", json={"token": viejo, "contrasena": "elegida-por-correo-9"}).status_code == 400
    assert client.post("/api/restablecer", json={"token": nuevo, "contrasena": "elegida-por-correo-9"}).status_code == 200


def test_el_enlace_vence(app, client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    _pedir(client, "ana")
    token = _enlace(buzon).group(1)
    with app.app_context():
        TokenRecuperacion.query.update({"expira": int(time.time()) - 1})
        db.session.commit()
    assert client.post("/api/restablecer", json={"token": token, "contrasena": "elegida-por-correo-9"}).status_code == 400


@pytest.mark.parametrize("token", ["", "abc", "x" * 43, None, 123])
def test_token_invalido_se_rechaza(client, token):
    assert client.post("/api/restablecer", json={"token": token, "contrasena": "elegida-por-correo-9"}).status_code == 400


@pytest.mark.parametrize("contrasena", ["corta1", "solamenteletrasaaa", "ana-clave-2026"])
def test_la_contrasena_nueva_debe_cumplir_la_politica(client, creador_usuarios, buzon, contrasena):
    creador_usuarios("ana", correo="ana@correo.com")
    _pedir(client, "ana")
    token = _enlace(buzon).group(1)
    assert client.post("/api/restablecer", json={"token": token, "contrasena": contrasena}).status_code == 400
    # El enlace sigue vivo para intentarlo de nuevo.
    assert client.post("/api/restablecer", json={"token": token, "contrasena": "elegida-por-correo-9"}).status_code == 200


def test_con_2fa_activo_se_exige_el_codigo(app, client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    secreto = totp.generar_secreto()
    with app.app_context():
        usuario = Usuario.query.filter_by(usuario="ana").first()
        usuario.totp_secreto = totp.proteger(secreto, app.secret_key)
        usuario.totp_activo = True
        db.session.commit()
    _pedir(client, "ana")
    token = _enlace(buzon).group(1)

    sin_codigo = client.post("/api/restablecer", json={"token": token, "contrasena": "elegida-por-correo-9"})
    assert sin_codigo.status_code == 401 and sin_codigo.get_json()["requiere_2fa"] is True
    codigo = totp._codigo(secreto, int(time.time() // totp.PASO_SEGUNDOS))
    con_codigo = client.post("/api/restablecer", json={"token": token, "contrasena": "elegida-por-correo-9", "codigo": codigo})
    assert con_codigo.status_code == 200


def test_limite_de_solicitudes_por_cuenta(client, creador_usuarios, buzon):
    creador_usuarios("ana", correo="ana@correo.com")
    for _ in range(5):
        assert _pedir(client, "ana").status_code == 200
    assert len(buzon) == 3  # el 4.º y el 5.º no mandan más correos


def test_sin_app_url_y_con_host_ajeno_no_se_envia_el_enlace(app, client, creador_usuarios, buzon, monkeypatch):
    """Un Host falsificado no puede apuntar el enlace del correo a otro sitio."""
    monkeypatch.delenv("APP_URL", raising=False)
    app.testing = False  # como en producción
    creador_usuarios("ana", correo="ana@correo.com")
    respuesta = client.post(
        "/api/recuperar", json={"identificador": "ana"}, base_url="http://sitio-malicioso.com",
        headers={"Origin": "http://sitio-malicioso.com"},
    )
    assert respuesta.status_code == 200
    assert buzon == []


def test_app_url_se_usa_para_el_enlace(client, creador_usuarios, buzon, monkeypatch):
    monkeypatch.setenv("APP_URL", "https://mettav.ejemplo.com/")
    creador_usuarios("ana", correo="ana@correo.com")
    _pedir(client, "ana")
    assert "https://mettav.ejemplo.com/restablecer/" in buzon[-1][2]


def test_la_pagina_de_restablecer_no_se_guarda_en_cache(client):
    respuesta = client.get("/restablecer/" + "a" * 43)
    assert respuesta.status_code == 200
    assert respuesta.headers["Cache-Control"] == "no-store"
    assert respuesta.headers["Referrer-Policy"] == "no-referrer"


def test_el_login_enlaza_a_la_recuperacion(client):
    assert "/recuperar" in client.get("/").get_data(as_text=True)
    assert client.get("/recuperar").status_code == 200
