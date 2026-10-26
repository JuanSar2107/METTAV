from datetime import datetime, timezone

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


class MovimientoInventario(db.Model):
    __tablename__ = "movimientos_inventario"

    id = db.Column(db.Integer, primary_key=True)
    empleado = db.Column(db.String(120), nullable=False)
    usuario = db.Column(db.String(80), nullable=False)
    articulo = db.Column(db.String(120), nullable=False)
    codigo_articulo = db.Column(db.String(24), nullable=False)
    categoria = db.Column(db.String(60), nullable=False, default="Sin categoría")
    tipo = db.Column(db.String(16), nullable=False, default="Retiro")
    cantidad = db.Column(db.Integer, nullable=False)
    unidad = db.Column(db.String(24), nullable=False)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        fecha_hora = self.fecha_hora
        if fecha_hora.tzinfo is None:
            fecha_hora = fecha_hora.replace(tzinfo=timezone.utc)
        return {
            "id": self.id,
            "empleado": self.empleado,
            "usuario": self.usuario,
            "articulo": self.articulo,
            "codigo_articulo": self.codigo_articulo,
            "categoria": self.categoria,
            "tipo": self.tipo,
            "cantidad": self.cantidad,
            "unidad": self.unidad,
            "fecha_hora": fecha_hora.isoformat(timespec="seconds"),
        }


class ConfiguracionSistema(db.Model):
    __tablename__ = "configuracion_sistema"

    clave = db.Column(db.String(80), primary_key=True)
    valor = db.Column(db.String(255), nullable=False)


class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(60), unique=True, nullable=False)

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre}
