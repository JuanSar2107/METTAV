from pathlib import Path
import os

from flask import Flask, jsonify
from sqlalchemy import inspect, text

from .extensions import db


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    database_path = Path(app.root_path).parent / "instance" / "mi_proyecto.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "mettav-dev-key-2026"),
        SQLALCHEMY_DATABASE_URI=database_url or f"sqlite:///{database_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )
    if test_config is not None:
        app.config.update(test_config)

    db.init_app(app)
    from .routes.inventory import inventario_bp
    from .routes.users import usuarios_bp

    app.register_blueprint(inventario_bp)
    app.register_blueprint(usuarios_bp)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    # En el despliegue API_ONLY no se publican login, dashboard ni plantillas.
    if os.getenv("API_ONLY", "0") != "1":
        from .routes.main import main_bp
        app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        user_columns = {column["name"] for column in inspect(db.engine).get_columns("usuarios")}
        if "es_admin" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE usuarios ADD COLUMN es_admin BOOLEAN NOT NULL DEFAULT 0")
                )

    @app.errorhandler(413)
    def archivo_supera_limite(_error):
        return jsonify(error="El archivo supera el límite de 5 MB."), 413

    return app
