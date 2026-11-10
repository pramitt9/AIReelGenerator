
from app import create_app
from app.extensions import db
from app.models import Scene

from app.services.audio.subtitles import generate_word_timestamps
from app.services.video_rendering.timeline_builder import build_timeline
from app.services.video_rendering.video_renderer import render_video


def main():
    app = create_app()

    with app.app_context():
        scene_records = (
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
            for scene in scene_records
        ]

    print("Generating word timestamps...")

    timestamps = generate_word_timestamps(
        "storage/audio/project_9999/narration.mp3"
    )

    print("Building synchronized timeline...")

    timeline = build_timeline(scenes, timestamps)

    print("Rendering video...")

    result = render_video(
        timeline=timeline,
        output_path="storage/rendered/project_4/timeline_video.mp4"
    )

    print("\nRendering successful!")
    print(f"Output: {result['output_path']}")
    print(f"Size: {result['file_size'] / (1024 * 1024):.2f} MB")
    print(f"Resolution: {result['resolution']}")
    print(f"FPS: {result['fps']}")
    print(f"Duration: {result['duration']:.3f} seconds")


if __name__ == "__main__":
    main()
