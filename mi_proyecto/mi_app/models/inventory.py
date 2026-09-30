from mi_app.extensions import db


class ArticuloInventario(db.Model):
    __tablename__ = "articulos_inventario"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(24), unique=True, nullable=False)
    nombre = db.Column(db.String(120), nullable=False)
    categoria = db.Column(db.String(60), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    unidad = db.Column(db.String(24), nullable=False, default="unidades")
    ubicacion = db.Column(db.String(80), nullable=False)
    imagen_url = db.Column(db.String(500), nullable=False)


class ConfiguracionSistema(db.Model):
    __tablename__ = "configuracion_sistema"

    clave = db.Column(db.String(80), primary_key=True)
    valor = db.Column(db.String(255), nullable=False)