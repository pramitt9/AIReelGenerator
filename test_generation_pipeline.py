
from unittest.mock import patch
from app import create_app
from app.extensions import db
from app.models import User, Project, Scene, GenerationJob
from app.services.generation.generation_pipeline import generate_project_video


app = create_app()
app.config["TESTING"] = True

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


def main():
    with app.app_context():
        db.create_all()

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
            user_id=user.id
        )

        db.session.add(project)
        db.session.commit()

        project_id = project.id

        # Simulate footage processing and create real scene records.
        def fake_process_storyboard(project_id, storyboard):
            for item in storyboard["scenes"]:
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

        with (
            patch(
                "app.services.generation.generation_pipeline.generate_script",
                return_value=storyboard
            ),
            patch(
                "app.services.generation.generation_pipeline.process_storyboard",
                side_effect=fake_process_storyboard
            ),
            patch(
                "app.services.generation.generation_pipeline.generate_narration",
                return_value={"audio_path": "mock_narration.mp3"}
            ),
            patch(
                "app.services.generation.generation_pipeline.generate_word_timestamps",
                return_value=mock_timestamps
            ),
            patch(
                "app.services.generation.generation_pipeline.render_video",
                return_value={
                    "output_path": "mock_silent_video.mp4",
                    "file_size": 1000,
                    "duration": 5.0,
                    "scene_count": 2,
                    "scene_motions": [
                        {"scene_number": 1, "camera_motion": "zoom_in"},
                        {"scene_number": 2, "camera_motion": "pan"}
                    ]
                }
            ),
            patch(
                "app.services.generation.generation_pipeline.render_subtitles",
                return_value={
                    "output_path": "mock_final_reel.mp4",
                    "file_size": 5000,
                    "word_count": 13,
                    "caption_groups": 3
                }
            )
        ):
            result = generate_project_video(project_id)

        print("\n===== PIPELINE RESULT =====")
        print(result)

        saved_project = db.session.get(Project, project_id)
        saved_job = db.session.get(GenerationJob, result["job_id"])

        print("\n===== DATABASE VERIFICATION =====")
        print("Project status:", saved_project.status)
        print("Job status:", saved_job.status)
        print("Job progress:", saved_job.progress)
        print("Saved scenes:", len(saved_project.scenes))

        assert saved_project.status == "completed"
        assert saved_job.status == "completed"
        assert saved_job.progress == 100
        assert len(saved_project.scenes) == 2

        assert [
            scene.camera_motion for scene in saved_project.scenes
        ] == ["zoom_in", "pan"]

        print("\nAll generation pipeline checks passed!")

        # Clean up test records.
        db.session.delete(project)
        db.session.delete(user)
        db.session.commit()
        db.session.remove()


if __name__ == "__main__":
    main()
