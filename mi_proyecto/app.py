import os
import secrets
from pathlib import Path

from flask import Flask

from mi_app.extensions import db
from mi_app.models import Usuario
from mi_app.routes import usuarios_bp

app = Flask(__name__, instance_relative_config=True)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{Path(app.instance_path) / 'mi_proyecto.sqlite3'}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db.init_app(app)
app.register_blueprint(usuarios_bp)

with app.app_context():
    db.create_all()


@app.get("/")
def inicio() -> str:
    return "La aplicación Flask está funcionando."


if __name__ == "__main__":
    app.run(debug=True)
