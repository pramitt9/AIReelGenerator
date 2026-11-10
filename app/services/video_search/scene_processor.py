
import os

from app.extensions import db
from app.models import Scene
from app.services.video_search.pixabay import search_videos
from app.services.video_search.asset_selector import select_best_video
from app.services.storage.media_storage import download_video


def process_storyboard(project_id: int, storyboard: dict) -> dict:
    """
    Process every storyboard scene:
    1. Create or retrieve its database record.
    2. Search Pixabay.
    3. Select suitable footage.
    4. Download the selected asset.
    5. Save metadata and processing status.
    """

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

    for index, scene_data in enumerate(scenes_data, start=1):

        scene_number = scene_data.get("scene_number", index)

        narration = scene_data.get("narration", "").strip()
        visual_description = scene_data.get(
            "visual_description", ""
        ).strip()

        duration = scene_data.get("duration", 5)
        visual_type = scene_data.get(
            "visual_type", "stock_video"
        )

        if not narration or not visual_description:
            summary["failed"] += 1
            summary["results"].append({
                "scene_number": scene_number,
                "status": "failed",
                "error": "Missing narration or visual description."
            })
            continue

        try:
            # Find an existing scene or create one.
            scene = Scene.query.filter_by(
                project_id=project_id,
                scene_number=scene_number
            ).first()

            if not scene:
                scene = Scene(
                    project_id=project_id,
                    scene_number=scene_number,
                    narration=narration,
                    visual_description=visual_description,
                    visual_type=visual_type,
                    duration=duration,
                    status="pending"
                )
                db.session.add(scene)
                db.session.commit()

            else:
                scene.narration = narration
                scene.visual_description = visual_description
                scene.visual_type = visual_type
                scene.duration = duration

            # Skip downloading an asset that already exists.
            if scene.asset_path and os.path.isfile(scene.asset_path):
                scene.status = "completed"
                db.session.commit()

                summary["completed"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "completed",
                    "asset_path": scene.asset_path,
                    "reused": True
                })
                continue

            # AI-generated visuals will be handled by a
            # separate provider later.
            if visual_type == "ai_generated":
                scene.status = "needs_visual"
                scene.error_message = "AI visual generation required."
                db.session.commit()

                summary["needs_visual"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "needs_visual"
                })
                continue

            scene.status = "processing"
            scene.error_message = None
            db.session.commit()

            # Search footage using the scene description.
            videos = search_videos(
                visual_description,
                per_page=10
            )

            if not videos:
                scene.status = "needs_visual"
                scene.error_message = "No matching stock footage found."
                db.session.commit()

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
                scene.error_message = "No suitable footage found."
                db.session.commit()

                summary["needs_visual"] += 1
                summary["results"].append({
                    "scene_number": scene_number,
                    "status": "needs_visual"
                })
                continue

            # Download selected footage.
            asset_path = download_video(
                best["url"],
                project_id=project_id,
                scene_number=scene_number
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

            # Persist the failure separately so one bad scene
            # doesn't stop the remaining scenes.
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
