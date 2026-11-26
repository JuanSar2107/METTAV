"""El administrador elimina a otros usuarios desde Usuarios y Empleados."""

from mi_app.extensions import db
from mi_app.models import MovimientoInventario, RegistroAcceso, SesionToken, Usuario


def _id(app, nombre):
    with app.app_context():
        return Usuario.query.filter_by(usuario=nombre).one().id_usuario


def test_admin_elimina_a_un_empleado_y_pierde_el_acceso(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    creador_usuarios("ana")
    empleada = app.test_client()
    empleada.post("/api/login", json={"usuario": "ana", "contrasena": "clave123"})
    assert empleada.get("/api/usuarios/me").status_code == 200

    iniciar_sesion("jefe")
    respuesta = client.delete(f"/api/usuarios/{_id(app, 'ana')}")
    assert respuesta.status_code == 200

    # Su sesión abierta deja de servir de inmediato y ya no puede volver a entrar.
    assert empleada.get("/api/usuarios/me").status_code == 401
    assert app.test_client().post("/api/login", json={"usuario": "ana", "contrasena": "clave123"}).status_code == 401
    with app.app_context():
        assert Usuario.query.filter_by(usuario="ana").first() is None
        assert SesionToken.query.count() == 1  # solo la del administrador
        evento = RegistroAcceso.query.filter_by(evento="usuario_eliminado").one()
        assert evento.usuario == "ana" and "jefe" in evento.detalle


def test_el_historial_se_conserva(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    creador_usuarios("ana")
    with app.app_context():
        db.session.add(MovimientoInventario(
            empleado="Ana", usuario="ana", articulo="Taladro", codigo_articulo="HER-001",
            categoria="General", tipo="Retiro", cantidad=1, unidad="unidades",
        ))
        db.session.commit()
    iniciar_sesion("jefe")
    assert client.delete(f"/api/usuarios/{_id(app, 'ana')}").status_code == 200
    with app.app_context():
        assert MovimientoInventario.query.filter_by(usuario="ana").count() == 1


def test_solo_un_administrador_puede_eliminar(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("ana")
    creador_usuarios("pedro", es_auxiliar=True)
    assert client.delete(f"/api/usuarios/{_id(app, 'ana')}").status_code == 401
    iniciar_sesion("pedro")
    assert client.delete(f"/api/usuarios/{_id(app, 'ana')}").status_code == 403
    with app.app_context():
        assert Usuario.query.filter_by(usuario="ana").first() is not None


def test_no_se_elimina_a_si_mismo_por_aqui(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    creador_usuarios("otro_jefe", es_admin=True)
    iniciar_sesion("jefe")
    assert client.delete(f"/api/usuarios/{_id(app, 'jefe')}").status_code == 409


def test_puede_eliminar_a_otro_administrador_si_queda_uno(app, client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    creador_usuarios("otro_jefe", es_admin=True)
    iniciar_sesion("jefe")
    assert client.delete(f"/api/usuarios/{_id(app, 'otro_jefe')}").status_code == 200
    with app.app_context():
        assert Usuario.query.filter_by(es_admin=True).count() == 1


def test_usuario_inexistente(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    iniciar_sesion("jefe")
    assert client.delete("/api/usuarios/9999").status_code == 404


def test_exige_token_csrf(app, creador_usuarios):
    creador_usuarios("jefe", es_admin=True)
    creador_usuarios("ana")
    sin_csrf = app.test_client()
    sin_csrf.post("/api/login", json={"usuario": "jefe", "contrasena": "clave123"})
    sin_csrf.delete_cookie("mettav_csrf")
    assert sin_csrf.delete(f"/api/usuarios/{_id(app, 'ana')}").status_code == 403


def test_el_boton_aparece_en_el_panel_del_admin(client, creador_usuarios, iniciar_sesion):
    creador_usuarios("jefe", es_admin=True)
    iniciar_sesion("jefe")
    html = client.get("/dashboard").get_data(as_text=True)
    assert 'id="user-detail-delete"' in html and "Eliminar usuario" in html
