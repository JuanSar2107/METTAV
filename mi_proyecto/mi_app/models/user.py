from werkzeug.security import check_password_hash, generate_password_hash

from mi_app.extensions import db


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id_usuario = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(256), nullable=False)
    es_admin = db.Column(db.Boolean, nullable=False, default=False)

    def establecer_contrasena(self, contrasena: str) -> None:
        self.contrasena_hash = generate_password_hash(contrasena)

    def verificar_contrasena(self, contrasena: str) -> bool:
        return check_password_hash(self.contrasena_hash, contrasena)
