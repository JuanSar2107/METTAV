from datetime import datetime, timezone

from mi_app.extensions import db

# Grupos de inventario tal como están creados en Sizfra (zona franca).
GRUPOS_INVENTARIO = {
    "001": "Activos oficina METTAV",
    "002": "Equipos de bodega",
    "003": "Equipos operativos bodega",
    "004": "Mercancía que ingresa para la prestación de un servicio",
}

PROCEDENCIAS = ("Nacional", "Extranjera")

# Para qué se integran las partes en una salida integrada.
PROCESOS_INTEGRACION = ("Fabricación", "Reparación", "Mantenimiento", "Overhaul", "Otro")

# Por dónde se registró un movimiento.
ORIGEN_MANUAL = "Manual"
ORIGEN_ALTA = "Alta de artículo"
ORIGEN_IMPORTACION = "Importación Excel"
ORIGEN_SALIDA_INTEGRADA = "Salida integrada"
ORIGEN_REMISION = "Remisión"

# Servicio que se le presta a la mercancía de clientes (grupo 004) y en qué va.
TIPOS_SERVICIO = ("Mantenimiento", "Reparación", "Overhaul", "Fabricación", "Materia prima", "Otro")
ESTADOS_SERVICIO = ("Recibido", "En servicio", "Terminado", "Entregado", "Cancelado")


class Remision(db.Model):
    """Remisión de salida: documento de entrega de mercancía a un cliente.

    Las líneas guardan una copia de los datos del artículo para que la
    remisión impresa no cambie si después se edita o elimina el artículo.
    """

    __tablename__ = "remisiones"

    id = db.Column(db.Integer, primary_key=True)
    consecutivo = db.Column(db.Integer, unique=True, nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    cliente_nombre = db.Column(db.String(160), nullable=False)
    cliente_nit = db.Column(db.String(32), nullable=False)
    contacto = db.Column(db.String(120))
    telefono = db.Column(db.String(60))
    email = db.Column(db.String(160))
    tipo_servicio = db.Column(db.String(30))
    documento_entrega = db.Column(db.String(120))
    observaciones = db.Column(db.Text)
    operacion_sizfra = db.Column(db.String(6))
    formulario = db.Column(db.String(24))
    empleado = db.Column(db.String(120), nullable=False)
    usuario = db.Column(db.String(80), nullable=False)
    fecha_hora = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    lineas = db.relationship(
        "RemisionLinea", back_populates="remision", order_by="RemisionLinea.id", cascade="all, delete-orphan"
    )
    anulado_en = db.Column(db.DateTime)
    anulado_por = db.Column(db.String(80))
    motivo_anulacion = db.Column(db.Text)

    @property
    def numero(self) -> str:
        return f"REM-{self.consecutivo:04d}"

    def to_dict(self):
        return {
            "id": self.id,
            "numero": self.numero,
            "fecha": self.fecha.isoformat(),
            "cliente_nombre": self.cliente_nombre,
            "cliente_nit": self.cliente_nit,
            "contacto": self.contacto,
            "telefono": self.telefono,
            "email": self.email,
            "tipo_servicio": self.tipo_servicio,
            "documento_entrega": self.documento_entrega,
            "observaciones": self.observaciones,
            "operacion_sizfra": self.operacion_sizfra,
            "formulario": self.formulario,
            "empleado": self.empleado,
            "usuario": self.usuario,
            "fecha_hora": self.fecha_hora.replace(tzinfo=timezone.utc).isoformat(timespec="seconds"),
            "lineas": [linea.to_dict() for linea in self.lineas],
            "anulada": self.anulado_en is not None,
            "motivo_anulacion": self.motivo_anulacion,
        }


class RemisionLinea(db.Model):
    __tablename__ = "remision_lineas"

    id = db.Column(db.Integer, primary_key=True)
    id_remision = db.Column(db.Integer, db.ForeignKey("remisiones.id"), nullable=False)
    codigo = db.Column(db.String(24), nullable=False)
    descripcion = db.Column(db.String(400), nullable=False)
    unidad = db.Column(db.String(24), nullable=False)
    procedencia = db.Column(db.String(20))
    estado = db.Column(db.String(40))
    subpartida = db.Column(db.String(20))
    valor_fob_usd = db.Column(db.Numeric(14, 2))
    cantidad = db.Column(db.Integer, nullable=False)
    estado_servicio = db.Column(db.String(20))
    # Estado que tenía el artículo antes de la remisión, para devolverlo si se anula.
    estado_servicio_anterior = db.Column(db.String(20))
    remision = db.relationship("Remision", back_populates="lineas")

    def to_dict(self):
        return {
            "codigo": self.codigo,
            "descripcion": self.descripcion,
            "unidad": self.unidad,
            "procedencia": self.procedencia,
            "estado": self.estado,
            "subpartida": self.subpartida,
            "valor_fob_usd": float(self.valor_fob_usd) if self.valor_fob_usd is not None else None,
            "cantidad": self.cantidad,
            "estado_servicio": self.estado_servicio,
        }


class RegistroAuditoria(db.Model):
    """Acciones sobre el inventario que no son movimientos de stock.

    Crear, actualizar (por importación) y eliminar artículos, e importar el
    Excel. Se guarda el código del artículo como texto para que el registro
    sobreviva aunque el artículo se elimine.
    """

    __tablename__ = "registro_auditoria"

    id = db.Column(db.Integer, primary_key=True)
    accion = db.Column(db.String(40), nullable=False)
    codigo_articulo = db.Column(db.String(24), index=True)
    detalle = db.Column(db.Text)
    empleado = db.Column(db.String(120), nullable=False)
    usuario = db.Column(db.String(80), nullable=False)
    fecha_hora = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "accion": self.accion,
            "codigo_articulo": self.codigo_articulo,
            "detalle": self.detalle,
            "empleado": self.empleado,
            "usuario": self.usuario,
            "fecha_hora": self.fecha_hora.replace(tzinfo=timezone.utc).isoformat(timespec="seconds"),
        }


class SalidaIntegrada(db.Model):
    """Una salida en la que a un equipo se le integraron partes del inventario.

    Cada artículo que sale (el equipo principal y cada parte) queda como un
    MovimientoInventario de tipo "Retiro" ligado a esta salida.
    """

    __tablename__ = "salidas_integradas"

    id = db.Column(db.Integer, primary_key=True)
    proceso = db.Column(db.String(20), nullable=False)
    # Equipo al que se integraron las partes (p. ej. "Banco ref. SER-2026-09-29").
    referencia = db.Column(db.String(120), nullable=False)
    observaciones = db.Column(db.Text)
    operacion_sizfra = db.Column(db.String(6))
    formulario = db.Column(db.String(24))
    empleado = db.Column(db.String(120), nullable=False)
    usuario = db.Column(db.String(80), nullable=False)
    fecha_hora = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    movimientos = db.relationship("MovimientoInventario", back_populates="salida", order_by="MovimientoInventario.id")
    anulado_en = db.Column(db.DateTime)
    anulado_por = db.Column(db.String(80))
    motivo_anulacion = db.Column(db.Text)

    def to_dict(self):
        fecha_hora = self.fecha_hora.replace(tzinfo=timezone.utc)
        return {
            "id": self.id,
            "proceso": self.proceso,
            "referencia": self.referencia,
            "observaciones": self.observaciones,
            "operacion_sizfra": self.operacion_sizfra,
            "formulario": self.formulario,
            "empleado": self.empleado,
            "usuario": self.usuario,
            "fecha_hora": fecha_hora.isoformat(timespec="seconds"),
            "movimientos": [movimiento.to_dict() for movimiento in self.movimientos],
            "anulada": self.anulado_en is not None,
            "motivo_anulacion": self.motivo_anulacion,
        }


class ArticuloInventario(db.Model):
    __tablename__ = "articulos_inventario"

    id = db.Column(db.Integer, primary_key=True)
    # Código ZF: el que se registra en Sizfra y el que se da de baja (p. ej. ZF-MAQ-CO-001).
    codigo = db.Column(db.String(24), unique=True, nullable=False)
    # Código interno de METTAV (p. ej. MAQ-BOD-CO-001).
    codigo_interno = db.Column(db.String(32))
    grupo = db.Column(db.String(3))
    tipo = db.Column(db.String(8))
    marca = db.Column(db.String(80))
    subpartida = db.Column(db.String(20))
    valor_fob_usd = db.Column(db.Numeric(14, 2))
    procedencia = db.Column(db.String(20))
    estado = db.Column(db.String(40))
    # Trazabilidad del activo (columnas del Excel de inventario).
    serial = db.Column(db.String(80))
    responsable = db.Column(db.String(120))
    fecha_ingreso = db.Column(db.Date)
    documento_soporte = db.Column(db.String(160))
    fecha_retiro = db.Column(db.Date)
    documento_retiro = db.Column(db.String(160))
    razon_retiro = db.Column(db.Text)
    # Mercancía de clientes (grupo 004): de quién es, qué servicio y en qué va.
    cliente = db.Column(db.String(160))
    tipo_servicio = db.Column(db.String(30))
    estado_servicio = db.Column(db.String(20))
    # Dado de baja: sale del inventario, pero conserva su código y su historia.
    dado_de_baja_en = db.Column(db.DateTime)
    dado_de_baja_por = db.Column(db.String(80))
    motivo_baja = db.Column(db.Text)
    nombre = db.Column(db.String(120), nullable=False)
    categoria = db.Column(db.String(60), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    stock_maximo = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    unidad = db.Column(db.String(24), nullable=False, default="unidades")
    ubicacion = db.Column(db.String(80), nullable=False)
    imagen_url = db.Column(db.String(500), nullable=False)
    imagen_url_2 = db.Column(db.String(500))
    imagen_url_3 = db.Column(db.String(500))

    @property
    def imagenes(self) -> list[str]:
        """Las fotos propias del artículo; la imagen genérica de la bodega no cuenta."""
        return [
            url for url in (self.imagen_url, self.imagen_url_2, self.imagen_url_3)
            if url and not url.endswith("/images/workshop-bg.jpg")
        ]


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
    # Se guarda en UTC sin zona horaria, igual en SQLite y en PostgreSQL;
    # to_dict() vuelve a marcarla como UTC al enviarla al navegador.
    fecha_hora = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    # Operación y formulario de Sizfra con los que se registró el movimiento.
    operacion_sizfra = db.Column(db.String(6))
    formulario = db.Column(db.String(24))
    # Solo en salidas integradas: a cuál pertenece y si es el equipo o una parte.
    id_salida = db.Column(db.Integer, db.ForeignKey("salidas_integradas.id"))
    rol = db.Column(db.String(12))
    salida = db.relationship("SalidaIntegrada", back_populates="movimientos")
    # Por dónde se registró (ver ORIGENES_MOVIMIENTO) y la razón u observación.
    origen = db.Column(db.String(20))
    observaciones = db.Column(db.Text)
    # Solo en salidas por remisión.
    id_remision = db.Column(db.Integer, db.ForeignKey("remisiones.id"))
    remision = db.relationship("Remision")
    # Documento soporte del ingreso: nombre en disco y nombre original del archivo.
    documento_archivo = db.Column(db.String(80))
    documento_nombre = db.Column(db.String(200))
    # Anulación: el registro se conserva marcado y el stock se devuelve.
    anulado_en = db.Column(db.DateTime)
    anulado_por = db.Column(db.String(80))
    motivo_anulacion = db.Column(db.Text)

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
            "operacion_sizfra": self.operacion_sizfra,
            "formulario": self.formulario,
            "id_salida": self.id_salida,
            "rol": self.rol,
            "proceso": self.salida.proceso if self.salida else None,
            "referencia": self.salida.referencia if self.salida else None,
            "origen": self.origen,
            "observaciones": self.observaciones,
            "id_remision": self.id_remision,
            "documento_nombre": self.documento_nombre,
            "documento_url": f"/api/inventario/movimientos/{self.id}/documento" if self.documento_archivo else None,
            "anulado": self.anulado_en is not None,
            "anulado_por": self.anulado_por,
            "motivo_anulacion": self.motivo_anulacion,
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


class TraduccionTexto(db.Model):
    """Traducción guardada de un texto del inventario, para no pedirla dos veces."""

    __tablename__ = "traducciones_texto"

    clave = db.Column(db.String(64), primary_key=True)
    origen = db.Column(db.Text, nullable=False)
    ingles = db.Column(db.Text, nullable=False)
