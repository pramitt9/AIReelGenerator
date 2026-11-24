
from app import create_app
from app.extensions import db
from app.models import Scene
from app.services.audio.subtitles import generate_word_timestamps
from app.services.video_rendering.timeline_builder import build_timeline


def main():
    app = create_app()

    with app.app_context():
        scenes_db = (
            db.session.query(Scene)
            .filter_by(project_id=4)
            .order_by(Scene.scene_number)
            .all()
        )

        scenes = [
            {
                "scene_number": scene.scene_number,
                "narration": scene.narration,
                "asset_path": scene.asset_path
            }
            for scene in scenes_db
        ]

    audio_path = "storage/audio/project_9999/narration.mp3"

    print("Generating timestamps...")
    timestamps = generate_word_timestamps(audio_path)

    print("Building timeline...")
    timeline = build_timeline(scenes, timestamps)

    print("\nTIMELINE")
    print("=" * 50)

    for scene in timeline["scenes"]:
        print(f"\nScene {scene['scene_number']}")
        print(f"Narration: {scene['narration']}")
        print(f"Start: {scene['start']}s")
        print(f"End: {scene['end']}s")
        print(f"Duration: {scene['duration']}s")

    print("\nTotal duration:", timeline["total_duration"], "seconds")


if __name__ == "__main__":
    main()
