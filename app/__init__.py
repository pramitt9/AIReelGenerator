
from flask import Flask
from app.routes import register_routes
from config import Config
from app.extensions import db, login_manager


def create_app(config_overrides=None):
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )

    app.config.from_object(Config)

    # Apply test or environment-specific configuration
    # before initializing extensions.
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    register_routes(app)

    return app
