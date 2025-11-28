from flask import Flask

from .routes import bp as api_bp


def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.register_blueprint(api_bp)

    return app

