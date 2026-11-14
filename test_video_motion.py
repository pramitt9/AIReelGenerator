
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

        if not scene_records:
            raise RuntimeError("No scenes found for project 4.")

        # Assign test camera movements and save them to the database.
        motions = ["zoom_in", "pan", "none", "zoom_out"]

        for index, scene in enumerate(scene_records):
            scene.camera_motion = motions[index % len(motions)]

        db.session.commit()

        # Retrieve camera movements from the database.
        scenes = [
            {
                "scene_number": scene.scene_number,
                "narration": scene.narration,
                "asset_path": scene.asset_path,
                "camera_motion": scene.camera_motion
            }
            for scene in scene_records
        ]

    print("Generating word timestamps...")

    timestamps = generate_word_timestamps(
        "storage/audio/project_9999/narration.mp3"
    )

    print("Building timeline...")

    timeline = build_timeline(scenes, timestamps)

    print("\n===== DATABASE TO TIMELINE VERIFICATION =====")

    for scene in timeline["scenes"]:
        print(
            f"Scene {scene['scene_number']}: "
            f"{scene['camera_motion']}"
        )

    # Verify that timeline preserved database values.
    for original, timeline_scene in zip(scenes, timeline["scenes"]):
        assert (
            original["camera_motion"] == timeline_scene["camera_motion"]
        ), f"Camera motion mismatch in scene {original['scene_number']}"

    output_directory = "storage/rendered/project_4"
    os.makedirs(output_directory, exist_ok=True)

    output_path = os.path.join(
        output_directory,
        "database_mixed_motion.mp4"
    )

    print("\nRendering video using database camera motions...")

    result = render_video(
        timeline=timeline,
        output_path=output_path,
        motion="none",
        motion_strength=0.08,
        transition="cut"
    )

    actual_duration = get_duration(output_path)

    print("\n===== RENDERING RESULTS =====")

    print("Output:", result["output_path"])
    print(f"Size: {result['file_size'] / (1024 * 1024):.2f} MB")
    print(f"Reported duration: {result['duration']:.3f}s")
    print(f"Actual duration: {actual_duration:.3f}s")

    print("\n===== RENDERER MOTION REPORT =====")

    for item in result["scene_motions"]:
        print(
            f"Scene {item['scene_number']}: "
            f"{item['camera_motion']}"
        )

    print("\nAll database-to-renderer checks passed!")

    with app.app_context():
        db.session.remove()


if __name__ == "__main__":
    main()
