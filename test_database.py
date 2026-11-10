from app import create_app
from app.extensions import db
from app.models import User, Project, GenerationJob

app = create_app()

with app.app_context():

    db.create_all()

    # Create a user
    user = User(
        username="database_test",
        email="database_test@example.com"
    )
    user.set_password("test123456")

    db.session.add(user)
    db.session.flush()

    # Create a project belonging to that user
    project = Project(
        title="AI Reel Test",
        topic="The future of artificial intelligence",
        user=user
    )

    db.session.add(project)
    db.session.flush()

    # Create a generation job for that project
    job = GenerationJob(
        status="pending",
        progress=0,
        project=project
    )

    db.session.add(job)
    db.session.commit()

    # Verify relationships
    print("User:", user.username)
    print("Project:", project.title)
    print("Project owner:", project.user.username)
    print("Generation job:", job.id)
    print("Job's project:", job.project.title)
    print("User's projects:", user.projects)
    print("Project's jobs:", project.generation_jobs)