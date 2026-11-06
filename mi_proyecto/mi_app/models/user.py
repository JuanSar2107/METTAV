from werkzeug.security import check_password_hash, generate_password_hash

from mi_app.extensions import db


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id_usuario = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(256), nullable=False)
    es_admin = db.Column(db.Boolean, nullable=False, default=False)
    # Auxiliar de inventarios: opera y consulta, pero no crea códigos ni usuarios.
    es_auxiliar = db.Column(db.Boolean, nullable=False, default=False)
    nombre_completo = db.Column(db.String(120), nullable=True)
    correo = db.Column(db.String(254), unique=True, nullable=True)
    numero_identidad = db.Column(db.String(32), unique=True, nullable=True)
    telefono = db.Column(db.String(32), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)
    imagen_perfil = db.Column(db.String(500), nullable=True)

    @property
    def puede_operar(self) -> bool:
        """Ve historial, trazabilidad y reportes, y cambia el estado del servicio."""
        return self.es_admin or self.es_auxiliar

    @property
    def rol_clave(self) -> str:
        return "admin" if self.es_admin else "auxiliar" if self.es_auxiliar else "empleado"

    @property
    def rol_nombre(self) -> str:
        return {"admin": "Administrador", "auxiliar": "Auxiliar de inventarios", "empleado": "Empleado"}[self.rol_clave]

    def establecer_contrasena(self, contrasena: str) -> None:
        self.contrasena_hash = generate_password_hash(contrasena)

    def verificar_contrasena(self, contrasena: str) -> bool:
        return check_password_hash(self.contrasena_hash, contrasena)
