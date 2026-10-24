from werkzeug.security import check_password_hash, generate_password_hash

from mi_app.extensions import db


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id_usuario = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(256), nullable=False)
    es_admin = db.Column(db.Boolean, nullable=False, default=False)
    nombre_completo = db.Column(db.String(120), nullable=True)
    correo = db.Column(db.String(254), unique=True, nullable=True)
    numero_identidad = db.Column(db.String(32), unique=True, nullable=True)
    telefono = db.Column(db.String(32), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)
    imagen_perfil = db.Column(db.String(500), nullable=True)

    def establecer_contrasena(self, contrasena: str) -> None:
        self.contrasena_hash = generate_password_hash(contrasena)

    def verificar_contrasena(self, contrasena: str) -> bool:
        return check_password_hash(self.contrasena_hash, contrasena)
