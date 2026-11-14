
from app.services.video_rendering.video_renderer import render_video
from app.services.audio.subtitles import generate_word_timestamps
from app.services.video_rendering.timeline_builder import build_timeline
from app.models.scene import Scene
from app import create_app
from app.extensions import db


app = create_app()

with app.app_context():
    scenes = (
        Scene.query
        .filter_by(project_id=4)
        .order_by(Scene.scene_number)
        .all()
    )

    scene_data = [
        {
            "asset_path": scene.asset_path,
            "scene_number": scene.scene_number,
            "narration": scene.narration,
            "duration": scene.duration
        }
        for scene in scenes
    ]

    audio_path = "storage/audio/project_9999/narration.mp3"

    timestamps = generate_word_timestamps(audio_path)

    timeline = build_timeline(
        scene_data,
        timestamps
    )

    transitions = ["cut", "crossfade", "fadeblack"]

    for transition in transitions:
        print(f"\nRendering transition: {transition}")

        output_path = (
            f"storage/rendered/project_4/"
            f"transition_{transition}.mp4"
        )

        result = render_video(
            timeline=timeline,
            output_path=output_path,
            transition=transition,
            transition_duration=0.4
        )

        print("Success!")
        print(f"Output: {result['output_path']}")
        print(f"Size: {result['file_size'] / (1024 * 1024):.2f} MB")
        print(f"Duration: {result['duration']:.3f}s")
