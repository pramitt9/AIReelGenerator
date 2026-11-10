from flask import Flask
from app.routes import register_routes
from config import Config
from app.extensions import db,login_manager

def create_app():
    app=Flask(__name__)

    app.config.from_object(Config)
    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view="auth.login"
    register_routes(app)
    return app
