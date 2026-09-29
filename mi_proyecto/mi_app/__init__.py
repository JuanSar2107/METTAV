from pathlib import Path

from flask import Flask

from .extensions import db


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    database_path = Path(app.root_path).parent / "instance" / "mi_proyecto.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY="mettav-dev-key-2026",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config is not None:
        app.config.update(test_config)

    db.init_app(app)
    from .routes.main import main_bp
    from .routes.users import usuarios_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(usuarios_bp)

    with app.app_context():
        db.create_all()

    return app
