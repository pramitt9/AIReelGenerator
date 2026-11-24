
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import User, Project, Scene, GenerationJob
from app.services.generation.generation_pipeline import generate_project_video


app = create_app({
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False
})


storyboard = {
    "title": "Test Reel",
    "hook": "Testing the generation pipeline.",
    "scenes": [
        {
            "scene_number": 1,
            "narration": "Artificial intelligence is changing our world.",
            "visual_description": "A futuristic city with AI technology.",
            "visual_type": "stock_video",
            "duration": 5,
            "camera_motion": "zoom_in"
        },
        {
            "scene_number": 2,
            "narration": "Machines are learning new things every day.",
            "visual_description": "Robotic arms working in a modern factory.",
            "visual_type": "stock_video",
            "duration": 5,
            "camera_motion": "pan"
        }
    ]
}


mock_timestamps = {
    "language": "en",
    "duration": 5.0,
    "words": [
        {"word": "Artificial", "start": 0.0, "end": 0.4},
        {"word": "intelligence", "start": 0.4, "end": 0.9},
        {"word": "is", "start": 0.9, "end": 1.1},
        {"word": "changing", "start": 1.1, "end": 1.5},
        {"word": "our", "start": 1.5, "end": 1.7},
        {"word": "world.", "start": 1.7, "end": 2.1},
        {"word": "Machines", "start": 2.2, "end": 2.5},
        {"word": "are", "start": 2.5, "end": 2.7},
        {"word": "learning", "start": 2.7, "end": 3.1},
        {"word": "new", "start": 3.1, "end": 3.3},
        {"word": "things", "start": 3.3, "end": 3.6},
        {"word": "every", "start": 3.6, "end": 3.8},
        {"word": "day.", "start": 3.8, "end": 4.1}
    ]
}


def create_mock_file(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"mock test output")
    return str(path)


def fake_process_storyboard(project_id, storyboard_data):
    # Replace previous test scenes, just as the real processor
    # updates existing scene records.
    Scene.query.filter_by(project_id=project_id).delete(
        synchronize_session=False
    )

    for item in storyboard_data["scenes"]:
        scene = Scene(
            project_id=project_id,
            scene_number=item["scene_number"],
            narration=item["narration"],
            visual_description=item["visual_description"],
            visual_type=item["visual_type"],
            duration=item["duration"],
            camera_motion=item["camera_motion"],
            asset_path=f"mock_scene_{item['scene_number']}.mp4",
            status="completed"
        )
        db.session.add(scene)

    db.session.commit()

    return {
        "project_id": project_id,
        "total": 2,
        "completed": 2,
        "needs_visual": 0,
        "failed": 0,
        "results": []
    }


def fake_generate_narration(storyboard_data, project_id, output_path):
    create_mock_file(output_path)
    return {"audio_path": output_path}


def fake_mix_audio(
    narration_path,
    music_path,
    output_path,
    music_volume,
    voice_volume
):
    create_mock_file(output_path)
    return {
        "output_path": output_path,
        "file_size": 100,
        "duration": 5.0
    }


def fake_render_video(timeline, output_path, transition):
    create_mock_file(output_path)

    return {
        "output_path": output_path,
        "file_size": 1000,
        "duration": 5.0,
        "scene_count": 2,
        "scene_motions": [
            {"scene_number": 1, "camera_motion": "zoom_in"},
            {"scene_number": 2, "camera_motion": "pan"}
        ]
    }


def fake_render_subtitles(
    video_path,
    audio_path,
    words,
    output_path,
    subtitle_path
):
    create_mock_file(output_path)

    return {
        "output_path": output_path,
        "file_size": 5000,
        "word_count": 13,
        "caption_groups": 3
    }


def test_generation_pipeline():
    # Keep the temporary directory alive for the entire test.
    with TemporaryDirectory() as temp_dir:
        app.root_path = str(Path(temp_dir) / "app")

        with app.app_context():
            db.create_all()

            try:
                user = User(
                    username="pipeline_test",
                    email="pipeline_test@example.com"
                )
                user.set_password("testpassword123")

                db.session.add(user)
                db.session.commit()

                project = Project(
                    title="Pipeline Integration Test",
                    topic="Artificial Intelligence",
                    user_id=user.id,
                    script=json.dumps(storyboard)
                )

                db.session.add(project)
                db.session.commit()

                project_id = project.id

                with (
                    patch(
                        "app.services.generation.generation_pipeline.process_storyboard",
                        side_effect=fake_process_storyboard
                    ),
                    patch(
                        "app.services.generation.generation_pipeline.generate_narration",
                        side_effect=fake_generate_narration
                    ),
                    patch(
                        "app.services.generation.generation_pipeline.generate_word_timestamps",
                        return_value=mock_timestamps
                    ),
                    patch(
                        "app.services.generation.generation_pipeline.mix_audio",
                        side_effect=fake_mix_audio
                    ),
                    patch(
                        "app.services.generation.generation_pipeline.render_video",
                        side_effect=[
                            fake_render_video(
                                {}, str(Path(temp_dir) / "unused.mp4"), "cut"
                            ),
                            RuntimeError("Simulated video rendering failure"),
                            fake_render_video(
                                {}, str(Path(temp_dir) / "unused2.mp4"), "cut"
                            )
                        ]
                    ) as mock_renderer,
                    patch(
                        "app.services.generation.generation_pipeline.render_subtitles",
                        side_effect=fake_render_subtitles
                    )
                ):
                    # TEST 1: Successful generation.
                    print("\n===== TEST 1: INITIAL GENERATION =====")

                    first_result = generate_project_video(project_id)

                    first_video = Path(first_result["output_video"])

                    assert first_result["status"] == "completed"
                    assert first_video.is_file()
                    assert first_video.stat().st_size > 0

                    print("First generation passed.")
                    print("Original video:", first_video)

                    # TEST 2: Second generation fails during rendering.
                    print("\n===== TEST 2: FAILURE RECOVERY =====")

                    try:
                        generate_project_video(project_id)
                        raise AssertionError(
                            "Expected the second generation to fail."
                        )
                    except RuntimeError as exc:
                        assert "Simulated video rendering failure" in str(exc)
                        print("Expected rendering failure received.")

                    db.session.expire_all()

                    saved_project = db.session.get(Project, project_id)

                    jobs = (
                        GenerationJob.query
                        .filter_by(project_id=project_id)
                        .order_by(GenerationJob.id)
                        .all()
                    )

                    failed_job = jobs[1]

                    assert failed_job.status == "failed"
                    assert "Simulated video rendering failure" in (
                        failed_job.error_message
                    )
                    assert saved_project.status == "completed"
                    assert first_video.is_file()

                    print("Failed job status:", failed_job.status)
                    print("Project status:", saved_project.status)
                    print("Previous video still exists:", first_video.is_file())

                    # TEST 3: A subsequent generation succeeds.
                    print("\n===== TEST 3: RETRY AFTER FAILURE =====")

                    third_result = generate_project_video(project_id)

                    db.session.expire_all()

                    saved_project = db.session.get(Project, project_id)
                    jobs = (
                        GenerationJob.query
                        .filter_by(project_id=project_id)
                        .order_by(GenerationJob.id)
                        .all()
                    )

                    assert third_result["status"] == "completed"
                    assert jobs[2].status == "completed"
                    assert saved_project.status == "completed"
                    assert Path(third_result["output_video"]).is_file()
                    assert first_video.is_file()

                    print("Third generation passed.")
                    print("All job statuses:", [job.status for job in jobs])
                    print("Project status:", saved_project.status)

                    # Verify the final scene records.
                    saved_scenes = (
                        Scene.query
                        .filter_by(project_id=project_id)
                        .order_by(Scene.scene_number)
                        .all()
                    )

                    assert len(saved_scenes) == 2
                    assert [
                        scene.camera_motion for scene in saved_scenes
                    ] == ["zoom_in", "pan"]

                    print("\nAll pipeline and recovery tests passed!")

            finally:
                db.session.rollback()
                db.drop_all()
                db.session.remove()

