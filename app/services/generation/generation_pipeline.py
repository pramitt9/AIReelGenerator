
import json
import os
import socket

import psutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import update

from flask import current_app

from app.extensions import db
from app.models import Project, Scene, GenerationJob

from app.services.video_search.scene_processor import process_storyboard
from app.services.audio.tts import generate_narration
from app.services.audio.subtitles import generate_word_timestamps
from app.services.video_rendering.timeline_builder import build_timeline
from app.services.video_rendering.video_renderer import render_video
from app.services.video_rendering.subtitle_renderer import render_subtitles


class GenerationAlreadyRunningError(RuntimeError):
    """Raised when another request already owns this project's generation slot."""


def _process_is_same_worker(pid: int, expected_create_time: float):
    """
    Return True for the original worker, False when it is gone or the PID
    belongs to a different process, and None when process identity is unknown.
    """
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        or not isinstance(expected_create_time, (int, float))
    ):
        return None

    try:
        process = psutil.Process(pid)
        actual_create_time = process.create_time()
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    except psutil.AccessDenied:
        # Never recover a job when Windows does not let us verify its owner.
        return None
    except psutil.Error:
        return None

    # Allow a tiny tolerance for floating-point storage in SQLite.
    return abs(actual_create_time - float(expected_create_time)) <= 0.000001


def recover_stale_generation(project_id: int) -> bool:
    """
    Recover a generation only when its recorded local worker is confirmed dead.

    Jobs owned by another host, or legacy jobs without process ownership, are
    left untouched because their liveness cannot be established safely.
    """
    project = db.session.get(Project, project_id)
    if not project:
        return False

    active_job = (
        GenerationJob.query
        .filter_by(project_id=project_id, status="processing")
        .order_by(GenerationJob.id.desc())
        .first()
    )

    if active_job:
        if (
            not active_job.worker_pid
            or not active_job.worker_host
            or active_job.worker_create_time is None
        ):
            return False

        if active_job.worker_host != socket.gethostname():
            return False

        worker_is_same = _process_is_same_worker(
            active_job.worker_pid,
            active_job.worker_create_time
        )
        if worker_is_same is not False:
            # The original worker is alive, or its identity cannot be verified.
            return False

        # Compare-and-set prevents two recovery requests from finalizing
        # the same job concurrently.
        result = db.session.execute(
            update(GenerationJob)
            .where(
                GenerationJob.id == active_job.id,
                GenerationJob.status == "processing",
                GenerationJob.worker_pid == active_job.worker_pid,
                GenerationJob.worker_host == active_job.worker_host,
                GenerationJob.worker_create_time == active_job.worker_create_time
            )
            .values(
                status="failed",
                error_message="Generation worker stopped unexpectedly. "
                              "The abandoned job was recovered automatically.",
                completed_at=datetime.now(timezone.utc)
            )
            .execution_options(synchronize_session=False)
        )

        if result.rowcount != 1:
            db.session.rollback()
            return False

    elif project.status != "processing":
        return False

    # Restore the project status without removing any previous successful
    # output. A previous completed job counts only if its file still exists.
    previous_jobs = (
        GenerationJob.query
        .filter_by(project_id=project_id, status="completed")
        .all()
    )
    previous_video_exists = any(
        item.output_video and Path(item.output_video).is_file()
        for item in previous_jobs
    )

    project.status = "completed" if previous_video_exists else "failed"
    db.session.commit()
    current_app.logger.warning(
        "Recovered abandoned generation state for project %s", project_id
    )
    return True


def generate_project_video(project_id: int) -> dict:
    """Generate a complete video from a project's saved storyboard."""

    project = db.session.get(Project, project_id)

    if not project:
        raise ValueError(f"Project {project_id} not found.")

    if not project.script:
        raise ValueError(
            "No saved storyboard found. Generate a storyboard first."
        )

    # Recover a confirmed-dead local worker before rejecting a retry.
    recover_stale_generation(project_id)
    db.session.expire_all()
    project = db.session.get(Project, project_id)

    # Fast rejection for the common duplicate-request case.
    active_job = GenerationJob.query.filter_by(
        project_id=project_id,
        status="processing"
    ).first()

    if active_job:
        raise GenerationAlreadyRunningError(
            "A video generation job is already running for this project."
        )

    # Atomically claim the project row. A second request cannot also change
    # the status from a non-processing state to processing.
    reservation = db.session.execute(
        update(Project)
        .where(
            Project.id == project_id,
            Project.status != "processing"
        )
        .values(status="processing")
        .execution_options(synchronize_session=False)
    )

    if reservation.rowcount != 1:
        active_job = GenerationJob.query.filter_by(
            project_id=project_id,
            status="processing"
        ).first()

        if active_job:
            raise GenerationAlreadyRunningError(
                "A video generation job is already running for this project."
            )

        raise GenerationAlreadyRunningError(
            "This project is marked as processing but has no active job. "
            "Reset the project status before retrying generation."
        )

    # Reload the storyboard after acquiring the reservation so generation
    # always uses the latest committed version, not a pre-lock snapshot.
    db.session.refresh(project)

    if not project.script:
        project.status = "draft"
        db.session.commit()
        raise ValueError(
            "No saved storyboard found. Generate a storyboard first."
        )

    job = GenerationJob(
        project_id=project_id,
        status="processing",
        progress=0,
        worker_pid=os.getpid(),
        worker_host=socket.gethostname(),
        worker_create_time=psutil.Process(os.getpid()).create_time()
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

        # 6. Use narration directly as the final audio.
        audio_path = str(actual_narration_path)

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
            audio_path=audio_path,
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
