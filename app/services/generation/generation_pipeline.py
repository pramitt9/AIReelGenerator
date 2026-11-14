
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import Project, Scene, GenerationJob

from app.services.ai.script_generator import generate_script
from app.services.video_search.scene_processor import process_storyboard
from app.services.audio.tts import generate_narration
from app.services.audio.subtitles import generate_word_timestamps
from app.services.video_rendering.timeline_builder import build_timeline
from app.services.video_rendering.video_renderer import render_video
from app.services.video_rendering.subtitle_renderer import render_subtitles


def generate_project_video(project_id: int) -> dict:
    """
    Run the complete video-generation workflow for a project.

    Pipeline:
    1. Generate storyboard
    2. Find and download footage
    3. Generate narration
    4. Generate word timestamps
    5. Build timeline
    6. Render video
    7. Burn subtitles and combine narration
    """

    project = Project.query.get(project_id)

    if not project:
        raise ValueError(f"Project {project_id} not found.")

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
        # 1. Generate storyboard
        storyboard = generate_script(project.topic)

        project.script = json.dumps(storyboard)
        update_progress(10)

        # 2. Find and download scene footage
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

        # 3. Retrieve processed scenes from database
        database_scenes = (
            Scene.query
            .filter_by(project_id=project_id)
            .order_by(Scene.scene_number)
            .all()
        )

        if len(database_scenes) != len(storyboard["scenes"]):
            raise RuntimeError(
                "The number of processed scenes does not match "
                "the generated storyboard."
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

        # 4. Generate narration
        narration_result = generate_narration(
            storyboard,
            project_id
        )

        narration_path = narration_result["audio_path"]
        update_progress(55)

        # 5. Generate word-level timestamps
        timestamp_result = generate_word_timestamps(
            narration_path
        )

        update_progress(70)

        # 6. Build timeline
        timeline = build_timeline(
            scenes,
            timestamp_result
        )

        # 7. Render scene footage
        storage_dir = (
            Path(current_app.root_path).parent
            / "storage"
            / "rendered"
            / f"project_{project_id}"
        )

        storage_dir.mkdir(parents=True, exist_ok=True)

        silent_video_path = storage_dir / "silent_video.mp4"
        final_video_path = storage_dir / "final_reel.mp4"

        render_result = render_video(
            timeline,
            str(silent_video_path),
            transition="cut"
        )

        update_progress(85)

        # 8. Burn subtitles and add narration
        subtitle_result = render_subtitles(
            video_path=str(silent_video_path),
            audio_path=narration_path,
            words=timestamp_result["words"],
            output_path=str(final_video_path)
        )

        # 9. Mark job as completed
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
