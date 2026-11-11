"""Tests de las medidas de seguridad (mi_app/security.py y rutas protegidas)."""

import hashlib
import time

import jwt
import pytest

from mi_app import security, totp
from mi_app.extensions import db
from mi_app.models import EventoLimite, RegistroAcceso, SesionToken


def test_cabeceras_de_seguridad(client):
    respuesta = client.get("/")
    assert "frame-ancestors 'none'" in respuesta.headers["Content-Security-Policy"]
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"


def test_api_no_se_guarda_en_cache(client):
    assert client.get("/api/usuarios/me").headers["Cache-Control"] == "no-store"


def test_cookies_jwt_httponly_y_lax(creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    cookies = {c.split("=")[0]: c for c in iniciar_sesion("ana").headers.getlist("Set-Cookie")}
    assert set(cookies) == {"mettav_access", "mettav_refresh", "mettav_csrf"}
    for nombre in ("mettav_access", "mettav_refresh"):
        assert "HttpOnly" in cookies[nombre]  # el JavaScript no puede leer los JWT
    assert "HttpOnly" not in cookies["mettav_csrf"]  # este lo lee csrf.js
    for cookie in cookies.values():
        assert "SameSite=Lax" in cookie
        assert "Secure" not in cookie  # en HTTP local no se marca Secure


def test_cookie_secure_en_https(client, creador_usuarios):
    creador_usuarios("ana")
    respuesta = client.post(
        "/api/login",
        json={"usuario": "ana", "contrasena": "clave123"},
        base_url="https://localhost",
    )
    assert all("Secure" in c for c in respuesta.headers.getlist("Set-Cookie"))
    assert "includeSubDomains" in respuesta.headers["Strict-Transport-Security"]


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
    respuesta = client.put("/api/usuarios/me", json={"contrasena": "nueva-segura-123"})
    assert respuesta.status_code == 403
    respuesta = client.put("/api/usuarios/me", json={"contrasena": "nueva-segura-123", "contrasena_actual": "incorrecta"})
    assert respuesta.status_code == 403


@pytest.mark.parametrize(
    "contrasena",
    [
        "", "x" * 257,  # vacía o demasiado larga
    ],
)
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
        "/api/usuarios/me", json={"contrasena": "nueva-segura-123", "contrasena_actual": "clave123"}
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


def _jwt_falso(id_usuario, clave, algoritmo="HS256", tipo="access"):
    ahora = int(time.time())
    carga = {"iss": "mettav", "sub": str(id_usuario), "sid": "falsa", "jti": "x", "typ": tipo,
             "pwd": "x", "iat": ahora, "exp": ahora + 900}
    return jwt.encode(carga, clave, algorithm=algoritmo)


def test_jwt_firmado_con_clave_vieja_no_sirve(client, creador_usuarios):
    """Un JWT firmado con la antigua clave por defecto ya no da acceso."""
    id_admin = creador_usuarios("jefe", es_admin=True)
    vieja = hashlib.sha256(b"mettav-jwt-v1|mettav-dev-key-2026").digest()
    client.set_cookie("mettav_access", _jwt_falso(id_admin, vieja))
    assert client.get("/api/usuarios/me").status_code == 401


def test_jwt_sin_firma_no_sirve(client, creador_usuarios):
    id_admin = creador_usuarios("jefe", es_admin=True)
    client.set_cookie("mettav_access", _jwt_falso(id_admin, None, algoritmo="none"))
    assert client.get("/api/usuarios/me").status_code == 401


def test_jwt_firmado_bien_pero_sin_sesion_en_servidor_no_sirve(app, client, creador_usuarios):
    """Aunque la firma sea correcta, sin una sesión registrada en la BD no se entra."""
    id_admin = creador_usuarios("jefe", es_admin=True)
    with app.app_context():
        token = _jwt_falso(id_admin, security._clave_jwt())
    client.set_cookie("mettav_access", token)
    assert client.get("/api/usuarios/me").status_code == 401


def test_el_refresco_no_sirve_como_acceso(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    refresco = client.get_cookie("mettav_refresh").value
    otro = client.application.test_client()
    otro.set_cookie("mettav_access", refresco)
    assert otro.get("/api/usuarios/me").status_code == 401


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


# --------------------------------------------------------- ciclo de vida de los JWT

def _caducar_acceso(app, cliente):
    """Deja vencido el JWT de acceso del cliente (como si pasaran los 15 minutos)."""
    token = cliente.get_cookie("mettav_access").value
    with app.app_context():
        clave = security._clave_jwt()
        carga = jwt.decode(token, clave, algorithms=["HS256"], issuer="mettav", options={"verify_exp": False})
        carga["exp"] = int(time.time()) - 600
        carga["iat"] = carga["exp"] - 900
        cliente.set_cookie("mettav_access", jwt.encode(carga, clave, algorithm="HS256"))


def _sid(cliente):
    return jwt.decode(cliente.get_cookie("mettav_refresh").value, options={"verify_signature": False})["sid"]


def _fila(app, cliente):
    sid = _sid(cliente)
    with app.app_context():
        return SesionToken.query.filter_by(familia=sid).first()


def _modificar_fila(app, cliente, **campos):
    sid = _sid(cliente)
    with app.app_context():
        SesionToken.query.filter_by(familia=sid).update(campos)
        db.session.commit()


def test_logout_revoca_los_tokens_en_el_servidor(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    robados = {n: client.get_cookie(n).value for n in ("mettav_access", "mettav_refresh")}
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/usuarios/me").status_code == 401

    # Quien copió las cookies antes del logout tampoco entra, aunque no hayan vencido.
    ladron = app.test_client()
    for nombre, valor in robados.items():
        ladron.set_cookie(nombre, valor)
    assert ladron.get("/api/usuarios/me").status_code == 401


def test_acceso_vencido_se_renueva_con_el_refresco_rotandolo(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    refresco_inicial = client.get_cookie("mettav_refresh").value
    _caducar_acceso(app, client)

    assert client.get("/api/usuarios/me").status_code == 200
    assert client.get_cookie("mettav_refresh").value != refresco_inicial
    assert client.get("/api/usuarios/me").status_code == 200


def test_refresco_robado_y_reutilizado_cierra_toda_la_sesion(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    copiado = client.get_cookie("mettav_refresh").value
    _caducar_acceso(app, client)
    assert client.get("/api/usuarios/me").status_code == 200  # el usuario rota su refresco
    _modificar_fila(app, client, rotada_en=int(time.time()) - 600)  # pasó la ventana de tolerancia

    ladron = app.test_client()
    ladron.set_cookie("mettav_refresh", copiado)
    assert ladron.get("/api/usuarios/me").status_code == 401

    # La sesión legítima también queda revocada.
    _caducar_acceso(app, client)
    assert client.get("/api/usuarios/me").status_code == 401
    with app.app_context():
        assert RegistroAcceso.query.filter_by(evento="token_reutilizado").count() == 1


def test_dos_peticiones_a_la_vez_con_el_mismo_refresco_no_cierran_la_sesion(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    refresco = client.get_cookie("mettav_refresh").value
    _caducar_acceso(app, client)
    assert client.get("/api/usuarios/me").status_code == 200

    paralela = app.test_client()
    paralela.set_cookie("mettav_refresh", refresco)  # el navegador envió el viejo a la vez
    assert paralela.get("/api/usuarios/me").status_code == 200
    assert client.get("/api/usuarios/me").status_code == 200


def test_sesion_se_cierra_por_inactividad(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    _caducar_acceso(app, client)
    _modificar_fila(app, client, expira=int(time.time()) - 1)
    assert client.get("/api/usuarios/me").status_code == 401


def test_sesion_se_cierra_al_pasar_la_duracion_maxima(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    _modificar_fila(app, client, inicio=int(time.time()) - 13 * 3600)
    assert client.get("/api/usuarios/me").status_code == 401


def test_cambio_de_contrasena_revoca_las_demas_sesiones_en_la_bd(app, creador_usuarios):
    creador_usuarios("ana")
    a, b = app.test_client(), app.test_client()
    for cliente in (a, b):
        cliente.post("/api/login", json={"usuario": "ana", "contrasena": "clave123"})
    b.put("/api/usuarios/me", json={"contrasena": "nueva-segura-123", "contrasena_actual": "clave123"})
    assert _fila(app, a).revocada is True
    assert _fila(app, b).revocada is False


def test_contrasena_nueva_debe_ser_distinta(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana", contrasena="clave-segura-123")
    iniciar_sesion("ana", "clave-segura-123")
    respuesta = client.put(
        "/api/usuarios/me", json={"contrasena": "clave-segura-123", "contrasena_actual": "clave-segura-123"}
    )
    assert respuesta.status_code == 400


# ------------------------------------------------------------------------- CSRF

@pytest.mark.parametrize("cabecera", ["", "token-incorrecto"])
def test_csrf_exige_el_token_con_sesion(client, creador_usuarios, iniciar_sesion, cabecera):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.post("/api/logout", headers={"X-CSRF-Token": cabecera})
    assert respuesta.status_code == 403
    assert client.get("/api/usuarios/me").status_code == 200  # la sesión sigue viva


def test_csrf_no_afecta_a_las_lecturas(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    assert client.get("/api/usuarios/me", headers={"X-CSRF-Token": ""}).status_code == 200


# ----------------------------------------------------------------- limitador

def test_limitador_guarda_los_intentos_en_la_bd(app, client, creador_usuarios):
    creador_usuarios("ana")
    for _ in range(5):
        client.post("/api/login", json={"usuario": "ana", "contrasena": "mala"})
    with app.app_context():
        assert EventoLimite.query.filter(EventoLimite.clave.like("login:%")).count() == 5
        # Un limitador nuevo (como tras reiniciar la app) sigue viendo el bloqueo.
        assert security.LimitadorIntentos().espera("login:127.0.0.1:ana", 5, 15 * 60) > 0


# ---------------------------------------------------------- verificación en dos pasos

def _activar_2fa(client):
    secreto = client.post("/api/usuarios/me/2fa/iniciar", json={"contrasena": "clave123"}).get_json()["secreto"]
    paso = int(time.time() // totp.PASO_SEGUNDOS)
    respuesta = client.post("/api/usuarios/me/2fa/activar", json={"codigo": totp._codigo(secreto, paso)})
    assert respuesta.status_code == 200
    return secreto, paso


def test_2fa_exige_codigo_en_el_login(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    secreto, paso = _activar_2fa(client)
    client.post("/api/logout")

    sin_codigo = client.post("/api/login", json={"usuario": "ana", "contrasena": "clave123"})
    assert sin_codigo.status_code == 401 and sin_codigo.get_json()["requiere_2fa"] is True
    assert client.get_cookie("mettav_access") is None

    malo = client.post("/api/login", json={"usuario": "ana", "contrasena": "clave123", "codigo": "000000"})
    assert malo.status_code == 401

    codigo = totp._codigo(secreto, paso + 1)  # el del paso de la activación ya está usado
    bueno = client.post("/api/login", json={"usuario": "ana", "contrasena": "clave123", "codigo": codigo})
    assert bueno.status_code == 200

    # El mismo código no se puede reutilizar.
    client.post("/api/logout")
    repetido = client.post("/api/login", json={"usuario": "ana", "contrasena": "clave123", "codigo": codigo})
    assert repetido.status_code == 401


def test_2fa_se_desactiva_con_contrasena_y_codigo(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    secreto, paso = _activar_2fa(client)
    mal = client.post("/api/usuarios/me/2fa/desactivar", json={"contrasena": "clave123", "codigo": "000000"})
    assert mal.status_code == 400
    bien = client.post(
        "/api/usuarios/me/2fa/desactivar",
        json={"contrasena": "clave123", "codigo": totp._codigo(secreto, paso + 1)},
    )
    assert bien.status_code == 200
    client.post("/api/logout")
    assert iniciar_sesion("ana").status_code == 200


def test_totp_coincide_con_el_vector_de_la_rfc_6238():
    secreto = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890" en base32
    assert totp._codigo(secreto, 59 // 30) == "287082"


# ----------------------------------------------------------- bitácora de accesos

def test_bitacora_registra_accesos_y_solo_la_ve_un_admin(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    creador_usuarios("ana")
    client.post("/api/login", json={"usuario": "ana", "contrasena": "mala"})
    iniciar_sesion("ana")
    assert client.get("/api/accesos").status_code == 403
    client.post("/api/logout")

    iniciar_sesion("jefe")
    eventos = [(a["evento"], a["usuario"]) for a in client.get("/api/accesos").get_json()["accesos"]]
    assert ("login_fallido", "ana") in eventos
    assert ("login", "ana") in eventos
    solo_fallos = client.get("/api/accesos?solo_fallos=1").get_json()["accesos"]
    assert solo_fallos and all(not a["exito"] for a in solo_fallos)


# ------------------------------------------------- cookies de sesión, cambio forzado, TOTP cifrado

def test_cookies_son_de_sesion_del_navegador(creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    for cookie in iniciar_sesion("ana").headers.getlist("Set-Cookie"):
        assert "Max-Age" not in cookie and "Expires" not in cookie  # se borran al cerrar el navegador


def test_logout_borra_las_cookies(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    borradas = client.post("/api/logout").headers.getlist("Set-Cookie")
    assert len(borradas) == 3 and all("Max-Age=0" in c or "1970" in c for c in borradas)
    assert client.get("/dashboard").status_code == 302  # de vuelta al login


def test_usuario_creado_por_el_admin_debe_cambiar_la_contrasena(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    iniciar_sesion("jefe")
    client.post("/api/usuarios", json={"usuario": "laura", "contrasena": "clave-inicial-123"})
    client.post("/api/logout")

    assert client.post("/api/login", json={"usuario": "laura", "contrasena": "clave-inicial-123"}).status_code == 200
    # Con el cambio pendiente solo se puede cambiar la contraseña o salir.
    bloqueado = client.get("/api/inventario/categorias")
    assert bloqueado.status_code == 403 and bloqueado.get_json()["cambiar_contrasena"] is True
    assert "Cambiar" in client.get("/dashboard").get_data(as_text=True) or "contraseña" in client.get("/dashboard").get_data(as_text=True)
    assert client.get("/api/usuarios/me").status_code == 200

    cambio = client.put("/api/usuarios/me", json={"contrasena": "mi-clave-propia-456", "contrasena_actual": "clave-inicial-123"})
    assert cambio.status_code == 200
    assert client.get("/api/inventario/categorias").status_code == 200


def test_secreto_totp_se_guarda_cifrado(app, client, creador_usuarios, iniciar_sesion):
    from mi_app.models import Usuario

    creador_usuarios("ana")
    iniciar_sesion("ana")
    secreto = client.post("/api/usuarios/me/2fa/iniciar", json={"contrasena": "clave123"}).get_json()["secreto"]
    with app.app_context():
        guardado = Usuario.query.filter_by(usuario="ana").first().totp_secreto
        assert guardado.startswith("enc:") and secreto not in guardado
        assert totp.revelar(guardado, app.secret_key) == secreto
        assert totp.revelar(guardado, "otra-clave") is None


def test_docs_es_solo_para_administradores(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    assert client.get("/docs").status_code == 403
