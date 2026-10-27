"""Tests de las medidas de seguridad (mi_app/security.py y rutas protegidas)."""

import pytest
from flask.sessions import SecureCookieSessionInterface


def test_cabeceras_de_seguridad(client):
    respuesta = client.get("/")
    assert "frame-ancestors 'none'" in respuesta.headers["Content-Security-Policy"]
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"


def test_api_no_se_guarda_en_cache(client):
    assert client.get("/api/usuarios/me").headers["Cache-Control"] == "no-store"


def test_cookie_de_sesion_httponly_y_lax(creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    cookie = iniciar_sesion("ana").headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie  # en HTTP local no se marca Secure


def test_cookie_secure_en_https(client, creador_usuarios):
    creador_usuarios("ana")
    respuesta = client.post(
        "/api/login",
        json={"usuario": "ana", "contrasena": "clave123"},
        base_url="https://localhost",
    )
    assert "Secure" in respuesta.headers["Set-Cookie"]
    assert "Strict-Transport-Security" in respuesta.headers


@pytest.mark.parametrize(
    "cabeceras",
    [
        {"Origin": "https://sitio-malicioso.com"},
        {"Referer": "https://sitio-malicioso.com/x"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_csrf_rechaza_otro_origen(client, creador_usuarios, cabeceras):
    creador_usuarios("ana")
    respuesta = client.post("/api/login", json={"usuario": "ana", "contrasena": "clave123"}, headers=cabeceras)
    assert respuesta.status_code == 403


def test_csrf_acepta_mismo_origen(client, creador_usuarios):
    creador_usuarios("ana")
    respuesta = client.post(
        "/api/login", json={"usuario": "ana", "contrasena": "clave123"}, headers={"Origin": "http://localhost"}
    )
    assert respuesta.status_code == 200


def test_login_bloquea_tras_varios_fallos(client, creador_usuarios):
    creador_usuarios("ana")
    for _ in range(5):
        assert client.post("/api/login", json={"usuario": "ana", "contrasena": "mala"}).status_code == 401
    bloqueado = client.post("/api/login", json={"usuario": "ana", "contrasena": "clave123"})
    assert bloqueado.status_code == 429
    assert "Retry-After" in bloqueado.headers
    # Otro usuario desde la misma IP todavía puede entrar
    creador_usuarios("pedro")
    assert client.post("/api/login", json={"usuario": "pedro", "contrasena": "clave123"}).status_code == 200


def test_cambio_de_contrasena_requiere_la_actual(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.put("/api/usuarios/me", json={"contrasena": "nueva1234"})
    assert respuesta.status_code == 403
    respuesta = client.put("/api/usuarios/me", json={"contrasena": "nueva1234", "contrasena_actual": "incorrecta"})
    assert respuesta.status_code == 403


@pytest.mark.parametrize("contrasena", ["corta1", "solamenteletras", "1234567890"])
def test_contrasena_debil_rechazada(client, creador_usuarios, iniciar_sesion, contrasena):
    creador_usuarios("jefe", es_admin=True)
    iniciar_sesion("jefe")
    respuesta = client.post("/api/usuarios", json={"usuario": "nuevo", "contrasena": contrasena})
    assert respuesta.status_code == 400


def test_cambio_de_contrasena_cierra_otras_sesiones(app, creador_usuarios):
    creador_usuarios("ana")
    sesion_vieja = app.test_client()
    sesion_nueva = app.test_client()
    for cliente in (sesion_vieja, sesion_nueva):
        cliente.post("/api/login", json={"usuario": "ana", "contrasena": "clave123"})

    respuesta = sesion_nueva.put(
        "/api/usuarios/me", json={"contrasena": "nueva1234", "contrasena_actual": "clave123"}
    )
    assert respuesta.status_code == 200
    assert sesion_nueva.get("/api/usuarios/me").status_code == 200
    assert sesion_vieja.get("/api/usuarios/me").status_code == 401


def test_eliminar_cuenta_requiere_contrasena(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    assert client.delete("/api/usuarios/me").status_code == 403
    assert client.delete("/api/usuarios/me", json={"contrasena": "mala"}).status_code == 403
    assert client.get("/api/usuarios/me").status_code == 200


def test_no_se_puede_eliminar_el_unico_admin(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    iniciar_sesion("jefe")
    respuesta = client.delete("/api/usuarios/me", json={"contrasena": "clave123"})
    assert respuesta.status_code == 409


def test_sesion_falsificada_con_clave_vieja_no_sirve(app, client, creador_usuarios):
    """Una cookie firmada con la antigua clave por defecto ya no da acceso."""
    id_admin = creador_usuarios("jefe", es_admin=True)
    original = app.secret_key
    app.secret_key = "mettav-dev-key-2026"
    cookie = SecureCookieSessionInterface().get_signing_serializer(app).dumps({"id_usuario": id_admin})
    app.secret_key = original

    client.set_cookie("session", cookie)
    assert client.get("/api/usuarios/me").status_code == 401


@pytest.mark.parametrize("valor", [None, "", "cambia-esta-clave-en-produccion", "mettav-dev-key-2026"])
def test_clave_secreta_insegura_se_reemplaza(tmp_path, monkeypatch, valor):
    from mi_app.security import resolver_clave_secreta

    if valor is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", valor)
    clave = resolver_clave_secreta(tmp_path)
    assert clave != valor and len(clave) == 64
    # En el siguiente arranque se reutiliza la misma clave
    assert resolver_clave_secreta(tmp_path) == clave


def test_clave_secreta_configurada_se_respeta(tmp_path, monkeypatch):
    from mi_app.security import resolver_clave_secreta

    monkeypatch.setenv("SECRET_KEY", "una-clave-propia-muy-larga")
    assert resolver_clave_secreta(tmp_path) == "una-clave-propia-muy-larga"
    assert not (tmp_path / "secret_key").exists()


def test_asistente_limita_consultas(client, monkeypatch, creador_usuarios, iniciar_sesion):
    from mi_app import gemini

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(gemini, "consultar_gemini", lambda *_: "ok")
    creador_usuarios("ana")
    iniciar_sesion("ana")
    codigos = [client.post("/api/asistente/", json={"pregunta": "hola"}).status_code for _ in range(16)]
    assert codigos[:15] == [200] * 15
    assert codigos[15] == 429
