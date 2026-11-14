
import os

from app.extensions import db
from app.models import Scene

from app.services.video_search.pixabay import search_videos
from app.services.video_search.asset_selector import select_best_video
from app.services.storage.media_storage import (
    download_video,
    delete_video
)


def clear_scene_asset(scene: Scene) -> None:
    """Clear previously selected visual asset metadata."""

    scene.provider = None
    scene.provider_video_id = None
    scene.asset_url = None
    scene.asset_path = None
    scene.thumbnail_url = None
    scene.width = None
    scene.height = None


def cleanup_old_asset(asset_path: str, project_id: int) -> None:
    """Safely delete an old asset without interrupting processing."""

    if not asset_path:
        return

    try:
        delete_video(asset_path, project_id)
    except Exception:
        # Cleanup failure should not invalidate scene processing.
        pass


def process_storyboard(project_id: int, storyboard: dict) -> dict:
    """
    Process storyboard scenes.

    Existing footage is reused only when the visual description
    and visual type have not changed.

    Changes to narration, duration or camera motion do not require
    downloading new footage.

    Assets are stored using stable scene IDs, so reordering scenes
    cannot cause footage files to overwrite one another.
    """

    if not isinstance(storyboard, dict):
        raise ValueError("Invalid storyboard format.")

    scenes_data = storyboard.get("scenes", [])

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

    allowed_motions = {
        "none",
        "zoom_in",
        "zoom_out",
        "pan"
    }

    for index, scene_data in enumerate(scenes_data, start=1):

        if not isinstance(scene_data, dict):
            summary["failed"] += 1
            summary["results"].append({
                "scene_number": index,
                "status": "failed",
                "error": "Invalid scene data."
            })
            continue

        scene_number = scene_data.get("scene_number", index)

        narration = scene_data.get("narration", "")
        visual_description = scene_data.get(
            "visual_description", ""
        )

        duration = scene_data.get("duration", 5)
        visual_type = scene_data.get(
            "visual_type", "stock_video"
        )
        camera_motion = scene_data.get(
            "camera_motion", "none"
        )

        if not isinstance(narration, str):
            narration = ""

        if not isinstance(visual_description, str):
            visual_description = ""

        narration = narration.strip()
        visual_description = visual_description.strip()

        if camera_motion not in allowed_motions:
            camera_motion = "none"

        if (
            not narration
            or not visual_description
            or visual_type not in {"stock_video", "ai_generated"}
        ):
            summary["failed"] += 1
            summary["results"].append({
                "scene_number": scene_number,
                "status": "failed",
                "error": "Missing or invalid scene information."
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

                scene.narration = narration
                scene.visual_description = visual_description
                scene.visual_type = visual_type
                scene.duration = duration
                scene.camera_motion = camera_motion

            else:
                scene = Scene(
                    project_id=project_id,
                    scene_number=scene_number,
                    narration=narration,
                    visual_description=visual_description,
                    visual_type=visual_type,
                    duration=duration,
                    status="pending",
                    camera_motion=camera_motion
                )

                db.session.add(scene)

            # Commit first so newly created scenes receive an ID.
            db.session.commit()

            # Reuse existing footage if its file still exists.
            if scene.asset_path and os.path.isfile(scene.asset_path):
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

            # AI-generated visuals need a separate provider.
            if visual_type == "ai_generated":
                scene.status = "needs_visual"
                scene.error_message = (
                    "AI visual generation required."
                )
                db.session.commit()

                cleanup_old_asset(old_asset_path, project_id)

                summary["needs_visual"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "needs_visual"
                })

                continue

            scene.status = "processing"
            scene.error_message = None
            db.session.commit()

            # Search Pixabay.
            videos = search_videos(
                visual_description,
                per_page=10
            )

            if not videos:
                scene.status = "needs_visual"
                scene.error_message = (
                    "No matching stock footage found."
                )
                db.session.commit()

                cleanup_old_asset(old_asset_path, project_id)

                summary["needs_visual"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "needs_visual"
                })

                continue

            # Select the best candidate.
            best = select_best_video(
                videos,
                visual_description,
                target_duration=int(duration)
            )

            if not best:
                scene.status = "needs_visual"
                scene.error_message = (
                    "No suitable footage found."
                )
                db.session.commit()

                cleanup_old_asset(old_asset_path, project_id)

                summary["needs_visual"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "needs_visual"
                })

                continue

            # Download using the stable database scene ID.
            asset_path = download_video(
                best["url"],
                project_id=project_id,
                scene_id=scene.id
            )

            if not asset_path or not os.path.isfile(asset_path):
                raise RuntimeError(
                    "Downloaded footage could not be found."
                )

            # Save selected asset metadata.
            scene.provider = "pixabay"
            scene.provider_video_id = str(best["video_id"])
            scene.asset_url = best["url"]
            scene.asset_path = asset_path
            scene.thumbnail_url = best.get("thumbnail")
            scene.width = best.get("width")
            scene.height = best.get("height")
            scene.status = "completed"
            scene.error_message = None

            db.session.commit()

            # The stable scene-ID path may have been atomically
            # replaced by the new download. Never delete that path.
            if old_asset_path and old_asset_path != asset_path:
                cleanup_old_asset(old_asset_path, project_id)

            summary["completed"] += 1
            summary["results"].append({
                "scene_number": scene_number,
                "status": "completed",
                "video_id": best["video_id"],
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
