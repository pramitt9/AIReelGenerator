
from app import create_app
from app.extensions import db
from app.models import User, Project, Scene

app = create_app()

with app.app_context():
    db.create_all()

    user = User.query.first()

    if not user:
        user = User(
            username="scene_test",
            email="scene_test@example.com"
        )
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.commit()

    project = Project(
        title="Scene Model Test",
        topic="Artificial Intelligence",
        user_id=user.id
    )

    db.session.add(project)
    db.session.commit()

    scene = Scene(
        project_id=project.id,
        scene_number=1,
        narration="Artificial intelligence is changing the world.",
        visual_description="A futuristic city with intelligent machines.",
        visual_type="stock_video",
        duration=5
    )

    db.session.add(scene)
    db.session.commit()

    print("Scene created:", scene.id)
    print("Project:", scene.project.title)
    print("Scenes in project:", len(project.scenes))

    db.session.delete(project)
    db.session.commit()

    print("Project and associated scenes deleted successfully.")

    db.session.remove()
