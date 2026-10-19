"""Tests de autenticación y gestión de usuarios (/api/usuarios/*)."""

from io import BytesIO
from pathlib import Path


def test_login_con_credenciales_incorrectas(client, creador_usuarios):
    creador_usuarios("admin", contrasena="clave123", es_admin=True)
    respuesta = client.post("/api/login", json={"usuario": "admin", "contrasena": "incorrecta"})
    assert respuesta.status_code == 401


def test_login_correcto_establece_sesion(client, creador_usuarios, iniciar_sesion):
    id_usuario = creador_usuarios("ana", contrasena="clave123")
    respuesta = iniciar_sesion("ana", "clave123")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["usuario"]["usuario"] == "ana"

    me = client.get("/api/usuarios/me")
    assert me.status_code == 200
    assert me.get_json()["usuario"]["id_usuario"] == id_usuario


def test_login_sin_datos_400(client):
    respuesta = client.post("/api/login", data="sin-json", content_type="application/json")
    assert respuesta.status_code == 400


def test_me_sin_sesion_401(client):
    respuesta = client.get("/api/usuarios/me")
    assert respuesta.status_code == 401


def test_registrar_requiere_sesion(client):
    respuesta = client.post("/api/usuarios", json={"usuario": "nuevo", "contrasena": "clave123"})
    assert respuesta.status_code == 401


def test_registrar_usuario_normal_no_autorizado(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("normal", es_admin=False)
    iniciar_sesion("normal")
    respuesta = client.post("/api/usuarios", json={"usuario": "nuevo", "contrasena": "clave123"})
    assert respuesta.status_code == 403


def test_admin_registra_usuario(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")
    respuesta = client.post("/api/usuarios", json={"usuario": "nuevo", "contrasena": "clave123"})
    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()["usuario"]
    assert cuerpo["usuario"] == "nuevo"
    assert cuerpo["es_admin"] is False


def test_registrar_usuario_duplicado_409(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    creador_usuarios("duplicado")
    iniciar_sesion("admin")
    respuesta = client.post("/api/usuarios", json={"usuario": "duplicado", "contrasena": "clave123"})
    assert respuesta.status_code == 409


def test_registrar_datos_invalidos(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("admin", es_admin=True)
    iniciar_sesion("admin")

    r1 = client.post("/api/usuarios", json={"usuario": "x", "contrasena": "ab"})  # muy corta
    assert r1.status_code == 400

    r2 = client.post("/api/usuarios", json={"contrasena": "clave123"})  # falta usuario
    assert r2.status_code == 400

    r3 = client.post("/api/usuarios", data="sin-json", content_type="application/json")  # JSON inválido
    assert r3.status_code == 400


def test_logout_limpia_sesion(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    assert client.get("/api/usuarios/me").status_code == 200

    respuesta = client.post("/api/logout")
    assert respuesta.status_code == 200
    assert client.get("/api/usuarios/me").status_code == 401


def test_actualizar_propio_usuario(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.put("/api/usuarios/me", json={"usuario": "ana_nueva"})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["usuario"]["usuario"] == "ana_nueva"


def test_actualizar_con_usuario_en_uso_409(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    creador_usuarios("pedro")
    iniciar_sesion("ana")
    respuesta = client.patch("/api/usuarios/me", json={"usuario": "pedro"})
    assert respuesta.status_code == 409


def test_actualizar_contrasena(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.put("/api/usuarios/me", json={"contrasena": "nueva123"})
    assert respuesta.status_code == 200

    client.post("/api/logout")
    nuevo_login = client.post("/api/login", json={"usuario": "ana", "contrasena": "nueva123"})
    assert nuevo_login.status_code == 200


def test_actualizar_perfil_con_correo(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.post(
        "/api/usuarios/me/perfil",
        data={"nombre_completo": "Ana Pérez", "correo": "ana@correo.com"},
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["usuario"]["correo"] == "ana@correo.com"


def test_actualizar_perfil_correo_invalido(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.post("/api/usuarios/me/perfil", data={"correo": "no-es-correo"})
    assert respuesta.status_code == 400


def test_actualizar_perfil_correo_en_uso(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana", correo="ana@correo.com")
    creador_usuarios("pedro")
    iniciar_sesion("pedro")
    respuesta = client.post("/api/usuarios/me/perfil", data={"correo": "ana@correo.com"})
    assert respuesta.status_code == 409


def test_actualizar_perfil_con_imagen(client, app, creador_usuarios, iniciar_sesion, imagen_png):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.post(
        "/api/usuarios/me/perfil",
        data={"imagen_perfil": (BytesIO(imagen_png), "perfil.png")},
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 200
    url = respuesta.get_json()["usuario"]["imagen_perfil"]
    assert url.startswith("/static/images/profiles/")

    archivo = Path(app.static_folder) / "images" / "profiles" / Path(url).name
    assert archivo.exists()


def test_actualizar_perfil_imagen_invalida(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.post(
        "/api/usuarios/me/perfil",
        data={"imagen_perfil": (BytesIO(b"no soy una imagen"), "foto.png")},
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 400


def test_eliminar_cuenta(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    iniciar_sesion("ana")
    respuesta = client.delete("/api/usuarios/me")
    assert respuesta.status_code == 200
    assert client.get("/api/usuarios/me").status_code == 401