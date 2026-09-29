from flask import Flask


def create_app():
    app = Flask(__name__)

    from mi_app.routes.main import main

    app.register_blueprint(main)
    return app