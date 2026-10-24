"""Tests del primer administrador creado a partir del entorno."""

from mi_app import create_app
from mi_app.extensions import db
from mi_app.models import Usuario


def _crear_app(tmp_path):
    """Crea una app con BD temporal."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "clave-de-prueba",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'seed.sqlite3').as_posix()}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    return app


def test_sin_variables_no_crea_usuarios(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    app = _crear_app(tmp_path)
    with app.app_context():
        assert Usuario.query.count() == 0
        db.session.remove()
        db.drop_all()


def test_crea_admin_con_variables_de_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "superadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "clave-secreta")

    app = _crear_app(tmp_path)
    with app.app_context():
        usuario = Usuario.query.filter_by(usuario="superadmin").first()
        assert usuario is not None
        assert usuario.es_admin is True
        assert usuario.verificar_contrasena("clave-secreta") is True
        db.session.remove()
        db.drop_all()


def test_crea_admin_por_defecto_si_no_se_indica(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "clave-secreta")

    app = _crear_app(tmp_path)
    with app.app_context():
        assert Usuario.query.filter_by(usuario="admin", es_admin=True).count() == 1
        db.session.remove()
        db.drop_all()


def test_no_sobrescribe_un_usuario_existente(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "primera-clave")
    app = _crear_app(tmp_path)

    with app.app_context():
        Usuario.query.filter_by(usuario="admin").first().establecer_contrasena("cambiada-luego")
        db.session.commit()

    # Segundo arranque con otra contraseña: no debe pisar la existente.
    monkeypatch.setenv("ADMIN_PASSWORD", "otra-clave")
    app2 = _crear_app(tmp_path)
    with app2.app_context():
        usuario = Usuario.query.filter_by(usuario="admin").first()
        assert Usuario.query.count() == 1
        assert usuario.verificar_contrasena("cambiada-luego") is True
        assert usuario.verificar_contrasena("otra-clave") is False
        db.session.remove()
        db.drop_all()


def test_no_crea_admin_si_falta_la_contrasena(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    app = _crear_app(tmp_path)
    with app.app_context():
        assert Usuario.query.count() == 0
        db.session.remove()
        db.drop_all()
