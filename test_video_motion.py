
import os
import subprocess

from app import create_app
from app.extensions import db
from app.models import Scene

from app.services.audio.subtitles import generate_word_timestamps
from app.services.video_rendering.timeline_builder import build_timeline
from app.services.video_rendering.video_renderer import render_video


def get_duration(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ],
        capture_output=True,
        text=True,
        check=True
    )
    return float(result.stdout.strip())


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

    if not scenes:
        raise RuntimeError("No scenes found for project 4.")

    print("Generating word timestamps...")

    timestamps = generate_word_timestamps(
        "storage/audio/project_9999/narration.mp3"
    )

    print("Building timeline...")
    timeline = build_timeline(scenes, timestamps)

    os.makedirs("storage/rendered/project_4", exist_ok=True)

    motion_modes = ["none", "zoom_in", "zoom_out", "pan"]

    for motion in motion_modes:
        output_path = (
            f"storage/rendered/project_4/motion_{motion}.mp4"
        )

        print(f"\nRendering motion: {motion}")

        result = render_video(
            timeline=timeline,
            output_path=output_path,
            motion=motion,
            motion_strength=0.08,
            transition="cut"
        )

        actual_duration = get_duration(output_path)

        print(f"Output: {result['output_path']}")
        print(f"Size: {result['file_size'] / (1024 * 1024):.2f} MB")
        print(f"Reported duration: {result['duration']:.3f}s")
        print(f"Actual duration: {actual_duration:.3f}s")

    print("\nAll motion tests completed.")


if __name__ == "__main__":
    main()
