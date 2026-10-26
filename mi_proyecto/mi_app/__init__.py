import os
from pathlib import Path

from flask import Flask, jsonify
from sqlalchemy import inspect, text

from .extensions import db


def _sembrar_admin(app: Flask) -> None:
    """Crea el primer administrador si la base de datos aún no tiene uno.

    Se controla con las variables de entorno ADMIN_USER (por defecto "admin")
    y ADMIN_PASSWORD. Nunca sobrescribe un usuario que ya exista, por lo que
    los reinicios y los redespliegues no cambian la contraseña vigente.
    """
    nombre = (os.environ.get("ADMIN_USER") or "admin").strip()
    clave = os.environ.get("ADMIN_PASSWORD") or ""

    if not clave:
        # Solo avisa si alguien configuró el usuario sin definir la clave.
        if os.environ.get("ADMIN_USER"):
            app.logger.warning(
                "ADMIN_USER está definido pero falta ADMIN_PASSWORD: no se crea el administrador."
            )
        return

    from .models import Usuario

    if Usuario.query.filter_by(usuario=nombre).first() is not None:
        return

    usuario = Usuario(usuario=nombre, es_admin=True)
    usuario.establecer_contrasena(clave)
    db.session.add(usuario)
    db.session.commit()
    app.logger.info("Administrador inicial '%s' creado.", nombre)


def _sembrar_categorias(app: Flask) -> None:
    """Siembra las categorías por defecto y las que ya existan en los artículos."""
    from .models import ArticuloInventario, Categoria

    categorias_base = [
        "General",
        "Herramientas eléctricas",
        "Herramientas manuales",
        "Protección personal",
        "Consumibles",
    ]
    try:
        articulos_existentes = (
            db.session.query(ArticuloInventario.categoria)
            .distinct()
            .all()
        )
        articulos_cats = [c[0] for c in articulos_existentes if c[0]]
    except Exception:
        articulos_cats = []

    todas = []
    for cat in categorias_base + articulos_cats:
        c_clean = cat.strip()
        if c_clean and c_clean not in todas:
            todas.append(c_clean)

    for cat_nombre in todas:
        if not Categoria.query.filter_by(nombre=cat_nombre).first():
            db.session.add(Categoria(nombre=cat_nombre))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def create_app(test_config: dict | None = None) -> Flask:

    app = Flask(__name__)
    database_path = Path(app.root_path).parent / "instance" / "mi_proyecto.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "mettav-dev-key-2026"),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )
    if test_config is not None:
        app.config.update(test_config)

    db.init_app(app)
    from .routes.main import main_bp
    from .routes.inventory import inventario_bp
    from .routes.users import usuarios_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(usuarios_bp)

    with app.app_context():
        db.create_all()
        user_columns = {column["name"] for column in inspect(db.engine).get_columns("usuarios")}
        user_migrations = {
            "es_admin": "BOOLEAN NOT NULL DEFAULT 0",
            "nombre_completo": "VARCHAR(120)",
            "correo": "VARCHAR(254)",
            "numero_identidad": "VARCHAR(32)",
            "telefono": "VARCHAR(32)",
            "direccion": "VARCHAR(255)",
            "imagen_perfil": "VARCHAR(500)",
        }
        missing_columns = {
            column_name: column_type
            for column_name, column_type in user_migrations.items()
            if column_name not in user_columns
        }
        if missing_columns:
            with db.engine.begin() as connection:
                for column_name, column_type in missing_columns.items():
                    connection.execute(
                        text(f"ALTER TABLE usuarios ADD COLUMN {column_name} {column_type}")
                    )

        movement_columns = {
            column["name"]
            for column in inspect(db.engine).get_columns("movimientos_inventario")
        }
        if "categoria" not in movement_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE movimientos_inventario "
                        "ADD COLUMN categoria VARCHAR(60) NOT NULL DEFAULT 'Sin categoría'"
                    )
                )
        if "tipo" not in movement_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE movimientos_inventario "
                        "ADD COLUMN tipo VARCHAR(16) NOT NULL DEFAULT 'Retiro'"
                    )
                )

        indexes = inspect(db.engine).get_indexes("usuarios")
        constraints = inspect(db.engine).get_unique_constraints("usuarios")
        unique_columns = {
            tuple(index.get("column_names") or [])
            for index in indexes + constraints
            if index.get("unique") or index in constraints
        }
        for column_name in ("correo", "numero_identidad"):
            if (column_name,) not in unique_columns:
                with db.engine.begin() as connection:
                    connection.execute(
                        text(
                            f"CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_{column_name} "
                            f"ON usuarios ({column_name})"
                        )
                    )

        _sembrar_admin(app)
        _sembrar_categorias(app)

    @app.errorhandler(413)
    def archivo_supera_limite(_error):
        return jsonify(error="El archivo supera el límite de 5 MB."), 413

    return app
