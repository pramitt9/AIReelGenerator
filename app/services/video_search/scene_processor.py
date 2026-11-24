
import math
import os

from app.extensions import db
from app.models import Scene

from app.services.video_search.pixabay import search_videos
from app.services.video_search.asset_selector import select_best_video
from app.services.storage.media_storage import (
    download_video,
    delete_video
)


ALLOWED_MOTIONS = {"none", "zoom_in", "zoom_out", "pan"}
ALLOWED_VISUAL_TYPES = {"stock_video", "ai_generated"}


def clear_scene_asset(scene: Scene) -> None:
    """Clear previously selected visual asset metadata."""
    scene.provider = None
    scene.provider_video_id = None
    scene.asset_url = None
    scene.asset_path = None
    scene.thumbnail_url = None
    scene.width = None
    scene.height = None


def process_storyboard(project_id: int, storyboard: dict) -> dict:
    """Process storyboard scenes and obtain visual assets."""

    if not isinstance(storyboard, dict):
        raise ValueError("Invalid storyboard format.")

    scenes_data = storyboard.get("scenes")

    if not isinstance(scenes_data, list) or not scenes_data:
        raise ValueError("Storyboard contains no scenes.")

    summary = {
        "project_id": project_id,
        "total": len(scenes_data),
        "completed": 0,
        "needs_visual": 0,
        "failed": 0,
        "results": []
    }

    seen_numbers = set()

    for index, scene_data in enumerate(scenes_data, start=1):
        scene_number = (
            scene_data.get("scene_number", index)
            if isinstance(scene_data, dict)
            else None
        )

        if (
            not isinstance(scene_number, int)
            or isinstance(scene_number, bool)
            or scene_number < 1
            or scene_number in seen_numbers
        ):
            raise ValueError(
                "Storyboard contains invalid or duplicate scene numbers."
            )

        seen_numbers.add(scene_number)

        narration = scene_data.get("narration", "")
        visual_description = scene_data.get("visual_description", "")
        duration = scene_data.get("duration", 5)
        visual_type = scene_data.get("visual_type", "stock_video")
        camera_motion = scene_data.get("camera_motion", "none")

        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = 0

        if (
            not isinstance(narration, str)
            or not narration.strip()
            or not isinstance(visual_description, str)
            or not visual_description.strip()
            or not math.isfinite(duration)
            or duration < 3
            or duration > 8
            or visual_type not in ALLOWED_VISUAL_TYPES
            or camera_motion not in ALLOWED_MOTIONS
        ):
            summary["failed"] += 1
            summary["results"].append({
                "scene_number": scene_number,
                "status": "failed",
                "error": "Invalid scene information."
            })
            continue

        old_asset_path = None

        try:
            scene = Scene.query.filter_by(
                project_id=project_id,
                scene_number=scene_number
            ).first()

            if scene:
                visual_changed = (
                    scene.visual_description != visual_description
                    or scene.visual_type != visual_type
                )

                if visual_changed:
                    old_asset_path = scene.asset_path
                    clear_scene_asset(scene)

                scene.narration = narration.strip()
                scene.visual_description = visual_description.strip()
                scene.visual_type = visual_type
                scene.duration = duration
                scene.camera_motion = camera_motion

            else:
                scene = Scene(
                    project_id=project_id,
                    scene_number=scene_number,
                    narration=narration.strip(),
                    visual_description=visual_description.strip(),
                    visual_type=visual_type,
                    duration=duration,
                    camera_motion=camera_motion,
                    status="pending"
                )
                db.session.add(scene)

            db.session.commit()

            # Reuse existing footage if the file is still available.
            if (
                scene.provider == "pixabay"
                and scene.asset_path
                and os.path.isfile(scene.asset_path)
            ):
                scene.status = "completed"
                scene.error_message = None
                db.session.commit()

                summary["completed"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "completed",
                    "asset_path": scene.asset_path,
                    "reused": True
                })
                continue

            if scene.asset_path:
                old_asset_path = scene.asset_path
                clear_scene_asset(scene)

            scene.status = "processing"
            scene.error_message = None
            db.session.commit()

            # AI-generated scenes fall back to stock footage.
            query = visual_description.strip()

            if visual_type == "ai_generated":
                query = f"{query} cinematic video"

            videos = search_videos(query)

            if not videos:
                scene.status = "needs_visual"
                scene.error_message = (
                    "No matching Pixabay footage found. "
                    "Try a simpler visual description."
                )
                db.session.commit()

                if old_asset_path:
                    delete_video(old_asset_path, project_id)

                summary["needs_visual"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "needs_visual",
                    "error": scene.error_message
                })
                continue

            best = select_best_video(
                videos,
                visual_description,
                target_duration=round(duration)
            )

            if not best or not best.get("url"):
                scene.status = "needs_visual"
                scene.error_message = "No suitable Pixabay footage found."
                db.session.commit()

                if old_asset_path:
                    delete_video(old_asset_path, project_id)

                summary["needs_visual"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "needs_visual",
                    "error": scene.error_message
                })
                continue

            asset_path = download_video(
                best["url"],
                project_id=project_id,
                scene_id=scene.id
            )

            if not asset_path or not os.path.isfile(asset_path):
                raise RuntimeError("Downloaded video file is missing.")

            scene.provider = "pixabay"
            scene.provider_video_id = str(best.get("video_id", ""))
            scene.asset_url = best["url"]
            scene.asset_path = asset_path
            scene.thumbnail_url = best.get("thumbnail")
            scene.width = best.get("width")
            scene.height = best.get("height")
            scene.status = "completed"
            scene.error_message = None

            db.session.commit()

            if old_asset_path and old_asset_path != asset_path:
                delete_video(old_asset_path, project_id)

            summary["completed"] += 1
            summary["results"].append({
                "scene_number": scene_number,
                "status": "completed",
                "asset_path": asset_path,
                "reused": False
            })

        except Exception as exc:
            db.session.rollback()

            try:
                failed_scene = Scene.query.filter_by(
                    project_id=project_id,
                    scene_number=scene_number
                ).first()

                if failed_scene:
                    failed_scene.status = "failed"
                    failed_scene.error_message = str(exc)[:2000]
                    db.session.commit()

            except Exception:
                db.session.rollback()

            summary["failed"] += 1
            summary["results"].append({
                "scene_number": scene_number,
                "status": "failed",
                "error": str(exc)
            })

    return summary
