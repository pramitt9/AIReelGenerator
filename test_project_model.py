from app import create_app
from app.extensions import db
from app.models import User, Project

app = create_app()

with app.app_context():

    db.create_all()

    # Reuse the test user if it already exists
    user = User.query.filter_by(
        email="test@example.com"
    ).first()

    if not user:
        user = User(
            username="testuser",
            email="test@example.com"
        )
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.commit()

    # Create a reel project
    project = Project(
        title="AI and the Future",
        topic="How artificial intelligence is changing the world",
        user=user
    )

    db.session.add(project)
    db.session.commit()

    # Retrieve the project
    saved_project = Project.query.filter_by(
        title="AI and the Future"
    ).first()

    print("Project:", saved_project)
    print("Project owner:", saved_project.user.username)
    print("User's projects:", saved_project.user.projects)