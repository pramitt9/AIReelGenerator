
import json

from app import create_app
from app.extensions import db
from app.models import Project
from app.models.scene import Scene

app = create_app()

with app.app_context():

    project = db.session.get(Project, 7)

    if not project:
        raise ValueError("Project 7 was not found.")

    if not project.script:
        raise ValueError("Project has no saved storyboard.")

    storyboard = json.loads(project.script)
    scenes_data = storyboard.get("scenes", [])

    if not scenes_data:
        raise ValueError("No scenes found in saved storyboard.")

    # Remove existing scene records to avoid duplicates.
    Scene.query.filter_by(project_id=project.id).delete(
        synchronize_session=False
    )

    # Recreate individual scene records.
    for index, data in enumerate(scenes_data, start=1):
        scene = Scene(
            project_id=project.id,
            scene_number=index,
            narration=data["narration"],
            visual_description=data["visual_description"],
            visual_type=data.get("visual_type", "stock_video"),
            duration=float(data["duration"]),
            camera_motion=data.get("camera_motion", "none"),
            status="pending"
        )

        db.session.add(scene)

    db.session.commit()

    print(f"Migration successful! {len(scenes_data)} scenes saved.")

    for scene in Scene.query.filter_by(
        project_id=project.id
    ).order_by(Scene.scene_number).all():

        print(
            f"Scene {scene.scene_number}: "
            f"{scene.duration}s | {scene.camera_motion}"
        )
