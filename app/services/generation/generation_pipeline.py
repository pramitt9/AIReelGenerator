
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
    """Generate a complete video from a project's saved storyboard."""

    project = db.session.get(Project, project_id)

    if not project:
        raise ValueError(f"Project {project_id} not found.")

    if not project.script:
        raise ValueError(
            "No saved storyboard found. Generate a storyboard first."
        )

    # Prevent a second generation while this project already has an active job.
    active_job = GenerationJob.query.filter_by(
        project_id=project_id,
        status="processing"
    ).first()

    if active_job:
        raise RuntimeError(
            "A video generation job is already running for this project."
        )

    job = GenerationJob(
        project_id=project_id,
        status="processing",
        progress=0
    )

    db.session.add(job)
    project.status = "processing"
    db.session.commit()

    job_id = job.id

    storage_root = (
        Path(current_app.root_path).parent
        / "storage"
        / "rendered"
        / f"project_{project_id}"
    )

    # Each job gets isolated intermediate and output files.
    job_dir = storage_root / f"job_{job_id}"

    narration_path = job_dir / "narration.mp3"
    mixed_audio_path = job_dir / "final_audio.mp3"
    silent_video_path = job_dir / "silent_video.mp4"
    final_video_path = job_dir / "final_reel.mp4"
    subtitle_path = job_dir / "subtitles.ass"

    def update_progress(progress: int):
        job_record = db.session.get(GenerationJob, job_id)

        if not job_record:
            raise RuntimeError("Generation job could not be found.")

        job_record.progress = progress
        db.session.commit()

    try:
        job_dir.mkdir(parents=True, exist_ok=True)
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

        # 2. Find and process scene footage.
        scene_summary = process_storyboard(project_id, storyboard)

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

        # 3. Retrieve and validate processed scenes.
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

        expected_numbers = [
            scene.get("scene_number", index)
            for index, scene in enumerate(storyboard_scenes, start=1)
        ]

        actual_numbers = [
            scene.scene_number for scene in database_scenes
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

        # 4. Generate narration into this job's own directory.
        narration_result = generate_narration(
            storyboard,
            project_id,
            output_path=str(narration_path)
        )

        actual_narration_path = Path(narration_result["audio_path"])

        if not actual_narration_path.is_file():
            raise RuntimeError("Narration generation did not produce an audio file.")

        update_progress(55)

        # 5. Generate word-level timestamps.
        timestamp_result = generate_word_timestamps(
            str(actual_narration_path)
        )

        if not timestamp_result.get("words"):
            raise RuntimeError("No word-level subtitle timestamps were generated.")

        # 6. Mix narration with background music.
        music_path = (
            Path(current_app.root_path).parent
            / "storage"
            / "music"
            / "fight34.mp3"
        )

        audio_result = mix_audio(
            narration_path=str(actual_narration_path),
            music_path=str(music_path),
            output_path=str(mixed_audio_path),
            music_volume=0.18,
            voice_volume=1.0
        )

        update_progress(70)

        # 7. Build the scene timeline.
        timeline = build_timeline(
            scenes,
            timestamp_result,
            hook=hook,
            ending=ending
        )

        # 8. Render scene footage.
        render_result = render_video(
            timeline,
            str(silent_video_path),
            transition="cut"
        )

        update_progress(85)

        # 9. Burn subtitles and combine audio.
        subtitle_result = render_subtitles(
            video_path=str(silent_video_path),
            audio_path=audio_result["output_path"],
            words=timestamp_result["words"],
            output_path=str(final_video_path),
            subtitle_path=str(subtitle_path)
        )

        # Confirm the final output exists before marking the job successful.
        if not final_video_path.is_file() or final_video_path.stat().st_size == 0:
            raise RuntimeError("Final video was not created successfully.")

        # 10. Mark this job as completed.
        job_record = db.session.get(GenerationJob, job_id)
        project_record = db.session.get(Project, project_id)

        if not job_record or not project_record:
            raise RuntimeError("Could not retrieve the generation records.")

        job_record.status = "completed"
        job_record.progress = 100
        job_record.output_video = str(final_video_path.resolve())
        job_record.completed_at = datetime.now(timezone.utc)

        project_record.status = "completed"

        db.session.commit()

        # Remove intermediates after the completed video is safely recorded.
        for temporary_file in (
            actual_narration_path,
            mixed_audio_path,
            silent_video_path,
            subtitle_path
        ):
            try:
                temporary_file.unlink(missing_ok=True)
            except OSError:
                current_app.logger.warning(
                    "Could not remove intermediate file: %s",
                    temporary_file
                )

        return {
            "job_id": job_id,
            "project_id": project_id,
            "status": "completed",
            "output_video": str(final_video_path.resolve()),
            "file_size": subtitle_result["file_size"],
            "duration": render_result["duration"],
            "scene_count": render_result["scene_count"],
            "subtitle_word_count": subtitle_result["word_count"],
            "scene_motions": render_result["scene_motions"]
        }

    except Exception as exc:
        db.session.rollback()

        current_app.logger.exception(
            "Video generation failed for project %s, job %s",
            project_id,
            job_id
        )

        # Record the failure without hiding an earlier successful video.
        try:
            failed_job = db.session.get(GenerationJob, job_id)
            project_record = db.session.get(Project, project_id)

            if failed_job:
                failed_job.status = "failed"
                failed_job.error_message = str(exc)[:4000]

            if project_record:
                previous_jobs = (
                    GenerationJob.query
                    .filter_by(
                        project_id=project_id,
                        status="completed"
                    )
                    .filter(GenerationJob.id != job_id)
                    .all()
                )

                previous_video_exists = any(
                    old_job.output_video
                    and Path(old_job.output_video).is_file()
                    for old_job in previous_jobs
                )

                project_record.status = (
                    "completed" if previous_video_exists else "failed"
                )

            db.session.commit()

        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Could not persist failure status for job %s",
                job_id
            )

        raise
