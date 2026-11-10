
from app import create_app
from app.extensions import db
from app.models import Project, Scene
import json


def main():
    app = create_app()

    with app.app_context():
        project = db.session.get(Project, 4)

        if not project:
            print("Project 4 not found.")
            return

        print("\nPROJECT")
        print("=" * 50)
        print(f"ID: {project.id}")
        print(f"Title: {project.title}")
        print(f"Topic: {project.topic}")

        print("\nSTORED STORYBOARD")
        print("=" * 50)

        if project.script:
            try:
                storyboard = json.loads(project.script)
                print(json.dumps(storyboard, indent=2))
            except json.JSONDecodeError:
                print(project.script)
        else:
            print("No storyboard stored.")

        print("\nPROCESSED SCENES")
        print("=" * 50)

        scenes = (
            db.session.query(Scene)
            .filter_by(project_id=4)
            .order_by(Scene.scene_number)
            .all()
        )

        for scene in scenes:
            print(f"\nScene {scene.scene_number}")
            print(f"Narration: {scene.narration}")
            print(f"Duration: {scene.duration}")
            print(f"Asset: {scene.asset_path}")
            print(f"Status: {scene.status}")


if __name__ == "__main__":
    main()
