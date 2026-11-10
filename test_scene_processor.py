
from app import create_app
from app.extensions import db
from app.models import User, Project
from app.services.video_search.scene_processor import process_storyboard


app = create_app()

storyboard = {
    "title": "The Future of Artificial Intelligence",
    "hook": "AI is changing the world faster than we think.",
    "scenes": [
        {
            "scene_number": 1,
            "narration": "Artificial intelligence is transforming our cities.",
            "visual_description": "Futuristic smart city with technology",
            "visual_type": "stock_video",
            "duration": 5
        },
        {
            "scene_number": 2,
            "narration": "Machines are learning to perform complex tasks.",
            "visual_description": "Industrial robotic arms working in a factory",
            "visual_type": "stock_video",
            "duration": 5
        },
        {
            "scene_number": 3,
            "narration": "The future of AI is still being written.",
            "visual_description": "Computer scientist working with artificial intelligence",
            "visual_type": "stock_video",
            "duration": 5
        }
    ]
}


with app.app_context():

    db.create_all()

    user = User.query.first()

    if not user:
        user = User(
            username="processor_test",
            email="processor_test@example.com"
        )
        user.set_password("testpassword123")
        db.session.add(user)
        db.session.commit()

    project = Project(
        title="Scene Processor Test",
        topic="Artificial Intelligence",
        user_id=user.id
    )

    db.session.add(project)
    db.session.commit()

    project_id = project.id

    print("Processing project:", project_id)

    result = process_storyboard(project_id, storyboard)

    print("\n===== PROCESSING SUMMARY =====")
    print("Total:", result["total"])
    print("Completed:", result["completed"])
    print("Needs visual:", result["needs_visual"])
    print("Failed:", result["failed"])

    for item in result["results"]:
        print("\nScene:", item["scene_number"])
        print("Status:", item["status"])

        if item.get("asset_path"):
            print("Asset:", item["asset_path"])

        if item.get("error"):
            print("Error:", item["error"])

    print("\n===== DATABASE VERIFICATION =====")

    saved_project = db.session.get(Project, project_id)

    for scene in saved_project.scenes:
        print(
            scene.scene_number,
            scene.status,
            scene.provider_video_id,
            scene.asset_path
        )

    db.session.remove()
