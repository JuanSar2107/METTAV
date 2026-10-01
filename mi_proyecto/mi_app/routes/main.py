from flask import Blueprint, redirect, render_template, session, url_for

from mi_app.extensions import db
from mi_app.models import ArticuloInventario, ConfiguracionSistema, Usuario

main_bp = Blueprint('main', __name__)

_INVENTARIO_INICIAL = [
    {
        "codigo": "HER-001",
        "nombre": "Taladro inalámbrico",
        "categoria": "Herramientas eléctricas",
        "descripcion": "Taladro percutor inalámbrico de 20 V con mandril de 13 mm, batería recargable y estuche de transporte.",
        "stock": 12,
        "unidad": "unidades",
        "ubicacion": "Estante A1",
        "imagen_url": "https://images.unsplash.com/photo-1572981779307-38b8cabb2407?auto=format&fit=crop&w=900&q=82",
    },
    {
        "codigo": "HER-002",
        "nombre": "Llave de impacto",
        "categoria": "Herramientas eléctricas",
        "descripcion": "Llave de impacto para trabajo pesado con encastre de 1/2 pulgada y control de velocidad variable.",
        "stock": 7,
        "unidad": "unidades",
        "ubicacion": "Estante A2",
        "imagen_url": "https://images.unsplash.com/photo-1504148455328-c376907d081c?auto=format&fit=crop&w=900&q=82",
    },
    {
        "codigo": "HER-003",
        "nombre": "Juego de llaves combinadas",
        "categoria": "Herramientas manuales",
        "descripcion": "Juego de llaves combinadas métricas, fabricadas en acero al cromo vanadio y organizadas en soporte.",
        "stock": 24,
        "unidad": "juegos",
        "ubicacion": "Estante B1",
        "imagen_url": "https://images.unsplash.com/photo-1581783898377-1c85bf937427?auto=format&fit=crop&w=900&q=82",
    },
    {
        "codigo": "SEG-001",
        "nombre": "Casco de seguridad",
        "categoria": "Protección personal",
        "descripcion": "Casco industrial ajustable con arnés interno para protección en trabajos de construcción y taller.",
        "stock": 18,
        "unidad": "unidades",
        "ubicacion": "Estante C1",
        "imagen_url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?auto=format&fit=crop&w=900&q=82",
    },
    {
        "codigo": "SEG-002",
        "nombre": "Guantes de protección",
        "categoria": "Protección personal",
        "descripcion": "Guantes de trabajo con palma reforzada para mejorar el agarre y proteger las manos durante la manipulación.",
        "stock": 5,
        "unidad": "pares",
        "ubicacion": "Estante C2",
        "imagen_url": "https://images.unsplash.com/photo-1584820927498-cfe5211fd8bf?auto=format&fit=crop&w=900&q=82",
    },
    {
        "codigo": "CON-001",
        "nombre": "Disco de corte",
        "categoria": "Consumibles",
        "descripcion": "Disco abrasivo de corte para metal, compatible con esmeriladora angular de 4 1/2 pulgadas.",
        "stock": 32,
        "unidad": "unidades",
        "ubicacion": "Estante D1",
        "imagen_url": "https://images.unsplash.com/photo-1586864387967-d02ef85d93e8?auto=format&fit=crop&w=900&q=82",
    },
]


def _inventario_inicial():
    clave = "inventario_demo_inicializado"
    if db.session.get(ConfiguracionSistema, clave) is None:
        if db.session.query(ArticuloInventario.id).first() is None:
            db.session.add_all(ArticuloInventario(**articulo) for articulo in _INVENTARIO_INICIAL)
        db.session.add(ConfiguracionSistema(clave=clave, valor="1"))
        db.session.commit()
    return ArticuloInventario.query.order_by(ArticuloInventario.id).all()

@main_bp.route('/')
def login():
    id_usuario = session.get('id_usuario')
    if isinstance(id_usuario, int) and db.session.get(Usuario, id_usuario) is not None:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')


@main_bp.route('/dashboard')
def dashboard():
    id_usuario = session.get('id_usuario')
    usuario = db.session.get(Usuario, id_usuario) if isinstance(id_usuario, int) else None
    if usuario is None:
        session.clear()
        return redirect(url_for('main.login'))
    articulos = _inventario_inicial()
    return render_template(
        'dashboard.html',
        usuario=usuario,
        articulos=articulos,
        es_admin=usuario.es_admin,
    )
