
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import Project, Scene, GenerationJob

from app.services.video_search.scene_processor import process_storyboard
from app.services.audio.tts import generate_narration
from app.services.audio.subtitles import generate_word_timestamps
from app.services.video_rendering.timeline_builder import build_timeline
from app.services.video_rendering.video_renderer import render_video
from app.services.video_rendering.subtitle_renderer import render_subtitles
from app.services.audio.audio_mixer import mix_audio


def generate_project_video(project_id: int) -> dict:
    """
    Generate a complete video using the project's saved storyboard.

    Pipeline:
    1. Load the saved storyboard
    2. Find and download scene footage
    3. Retrieve processed scenes
    4. Generate narration, including hook and ending
    5. Generate word timestamps
    6. Mix narration with background music
    7. Build the scene timeline
    8. Render scene footage
    9. Burn subtitles and combine audio
    """

    project = Project.query.get(project_id)

    if not project:
        raise ValueError(f"Project {project_id} not found.")

    if not project.script:
        raise ValueError(
            "No saved storyboard found. Generate a storyboard first."
        )

    job = GenerationJob(
        project_id=project_id,
        status="processing",
        progress=0
    )

    db.session.add(job)
    project.status = "processing"
    db.session.commit()

    def update_progress(progress: int):
        job.progress = progress
        db.session.commit()

    try:
        # 1. Load and validate the saved storyboard.
        try:
            storyboard = json.loads(project.script)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("The saved storyboard contains invalid JSON.")

        if not isinstance(storyboard, dict):
            raise ValueError("The saved storyboard must be a JSON object.")

        storyboard_scenes = storyboard.get("scenes")

        if not isinstance(storyboard_scenes, list) or not storyboard_scenes:
            raise ValueError("The saved storyboard contains no scenes.")

        hook = storyboard.get("hook", "")
        ending = storyboard.get("ending", "")

        if not isinstance(hook, str) or not isinstance(ending, str):
            raise ValueError("The storyboard hook and ending must be text.")

        update_progress(10)

        # 2. Find and download scene footage.
        scene_summary = process_storyboard(
            project_id,
            storyboard
        )

        if scene_summary["failed"] or scene_summary["needs_visual"]:
            raise RuntimeError(
                "Some scenes could not obtain footage. "
                f"Completed: {scene_summary['completed']}, "
                f"Needs visual: {scene_summary['needs_visual']}, "
                f"Failed: {scene_summary['failed']}."
            )

        if scene_summary["completed"] != scene_summary["total"]:
            raise RuntimeError("Not all scenes were processed.")

        update_progress(40)

        # 3. Retrieve processed scenes from the database.
        database_scenes = (
            Scene.query
            .filter_by(project_id=project_id)
            .order_by(Scene.scene_number)
            .all()
        )

        if len(database_scenes) != len(storyboard_scenes):
            raise RuntimeError(
                "The number of processed scenes does not match "
                "the saved storyboard."
            )

        # Ensure the database and storyboard have matching scene numbers.
        expected_numbers = [
            scene.get("scene_number", index)
            for index, scene in enumerate(storyboard_scenes, start=1)
        ]

        actual_numbers = [
            scene.scene_number
            for scene in database_scenes
        ]

        if expected_numbers != actual_numbers:
            raise RuntimeError(
                "The saved storyboard and database scene order do not match."
            )

        scenes = [
            {
                "scene_number": scene.scene_number,
                "narration": scene.narration,
                "asset_path": scene.asset_path,
                "camera_motion": scene.camera_motion
            }
            for scene in database_scenes
        ]

        # 4. Generate narration, including hook and ending.
        narration_result = generate_narration(
            storyboard,
            project_id
        )

        narration_path = narration_result["audio_path"]

        update_progress(55)

        # 5. Generate word-level timestamps.
        timestamp_result = generate_word_timestamps(
            narration_path
        )

        # 6. Mix narration with background music.
        storage_dir = (
            Path(current_app.root_path).parent
            / "storage"
            / "rendered"
            / f"project_{project_id}"
        )

        storage_dir.mkdir(parents=True, exist_ok=True)

        music_path = (
            Path(current_app.root_path).parent
            / "storage"
            / "music"
            / "fight34.mp3"
        )

        mixed_audio_path = storage_dir / "final_audio.mp3"

        audio_result = mix_audio(
            narration_path=narration_path,
            music_path=str(music_path),
            output_path=str(mixed_audio_path),
            music_volume=0.18,
            voice_volume=1.0
        )

        update_progress(70)

        # 7. Build timeline, including hook and ending.
        timeline = build_timeline(
            scenes,
            timestamp_result,
            hook=hook,
            ending=ending
        )

        # 8. Render scene footage.
        silent_video_path = storage_dir / "silent_video.mp4"
        final_video_path = storage_dir / "final_reel.mp4"

        render_result = render_video(
            timeline,
            str(silent_video_path),
            transition="cut"
        )

        update_progress(85)

        # 9. Burn subtitles and combine narration.
        subtitle_result = render_subtitles(
            video_path=str(silent_video_path),
            audio_path=audio_result["output_path"],
            words=timestamp_result["words"],
            output_path=str(final_video_path)
        )

        # 10. Mark job as completed.
        job.status = "completed"
        job.progress = 100
        job.output_video = str(final_video_path.resolve())
        job.completed_at = datetime.now(timezone.utc)

        project.status = "completed"

        db.session.commit()

        return {
            "job_id": job.id,
            "project_id": project_id,
            "status": job.status,
            "output_video": job.output_video,
            "file_size": subtitle_result["file_size"],
            "duration": render_result["duration"],
            "scene_count": render_result["scene_count"],
            "subtitle_word_count": subtitle_result["word_count"],
            "scene_motions": render_result["scene_motions"]
        }

    except Exception as exc:
        db.session.rollback()

        # Persist the failed job and project status.
        job = db.session.get(GenerationJob, job.id)
        project = db.session.get(Project, project_id)

        if job:
            job.status = "failed"
            job.error_message = str(exc)[:4000]

        if project:
            project.status = "failed"

        db.session.commit()

        raise
