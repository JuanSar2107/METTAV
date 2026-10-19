"""Tests de los modelos de datos (cifrado de contraseñas y unicidad)."""

import pytest
from sqlalchemy.exc import IntegrityError

from mi_app.extensions import db
from mi_app.models import Usuario


def test_contrasena_se_almacena_cifrada(app):
    with app.app_context():
        usuario = Usuario(usuario="ana")
        usuario.establecer_contrasena("clave123")
        db.session.add(usuario)
        db.session.commit()

        cargado = db.session.get(Usuario, usuario.id_usuario)
        assert cargado.contrasena_hash != "clave123"
        assert cargado.verificar_contrasena("clave123") is True
        assert cargado.verificar_contrasena("otra-clave") is False


def test_usuario_duplicado_rechazado(app, creador_usuarios):
    with app.app_context():
        creador_usuarios("ana")
        with pytest.raises(IntegrityError):
            duplicado = Usuario(usuario="ana")
            duplicado.establecer_contrasena("clave123")
            db.session.add(duplicado)
            db.session.commit()