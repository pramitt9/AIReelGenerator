from app.routes.main import main
from app.routes.auth import auth
from app.routes.projects import projects

def register_routes(app):
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(projects)