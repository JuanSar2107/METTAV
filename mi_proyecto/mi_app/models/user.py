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
    # Verificación en dos pasos (TOTP). Solo exige código si totp_activo es True.
    totp_secreto = db.Column(db.String(255), nullable=True)  # cifrado (ver totp.proteger)
    totp_activo = db.Column(db.Boolean, nullable=False, default=False)
    totp_ultimo_paso = db.Column(db.BigInteger, nullable=True)
    # True hasta que el usuario cambie la contraseña que le dieron (o que es anterior a la política).
    cambio_requerido = db.Column(db.Boolean, nullable=False, default=False)

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


class SesionToken(db.Model):
    """Una sesión iniciada: familia de tokens de refresco que se puede revocar.

    El JWT de acceso dura pocos minutos; el de refresco se rota en cada uso y
    su `jti` vigente se guarda aquí, así el servidor puede cerrar la sesión
    (logout, cambio de contraseña) y detectar un token robado y reutilizado.
    """

    __tablename__ = "sesiones_token"

    id = db.Column(db.Integer, primary_key=True)
    familia = db.Column(db.String(32), unique=True, nullable=False)
    id_usuario = db.Column(db.Integer, nullable=False, index=True)
    jti_actual = db.Column(db.String(32), nullable=False)
    jti_anterior = db.Column(db.String(32), nullable=True)
    rotada_en = db.Column(db.BigInteger, nullable=False, default=0)
    inicio = db.Column(db.BigInteger, nullable=False)
    expira = db.Column(db.BigInteger, nullable=False)
    ultimo_uso = db.Column(db.BigInteger, nullable=False)
    revocada = db.Column(db.Boolean, nullable=False, default=False)
    ip = db.Column(db.String(64), nullable=True)
    agente = db.Column(db.String(200), nullable=True)


class RegistroAcceso(db.Model):
    """Bitácora de inicios de sesión, cierres y eventos sospechosos."""

    __tablename__ = "registro_accesos"

    id = db.Column(db.Integer, primary_key=True)
    momento = db.Column(db.DateTime, nullable=False, index=True)
    evento = db.Column(db.String(24), nullable=False)
    exito = db.Column(db.Boolean, nullable=False)
    usuario = db.Column(db.String(80), nullable=True)
    id_usuario = db.Column(db.Integer, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    agente = db.Column(db.String(200), nullable=True)
    detalle = db.Column(db.String(200), nullable=True)


class EventoLimite(db.Model):
    """Intentos contados por el limitador; en la BD para sobrevivir reinicios."""

    __tablename__ = "eventos_limite"

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(200), nullable=False, index=True)
    momento = db.Column(db.Float, nullable=False)
