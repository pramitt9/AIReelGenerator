
import json

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Project, GenerationJob
from app.models.scene import Scene

from app.services.ai.script_generator import generate_script
from app.services.generation.generation_pipeline import generate_project_video


projects = Blueprint(
    "projects",
    __name__,
    url_prefix="/api/projects"
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

ALLOWED_MOTIONS = {
    "none",
    "zoom_in",
    "zoom_out",
    "pan"
}

ALLOWED_VISUAL_TYPES = {
    "stock_video",
    "ai_generated"
}


def get_owned_project(project_id):
    return Project.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first()


def load_storyboard(project):
    """Load and validate the saved storyboard JSON."""

    if not project.script:
        raise ValueError("No saved storyboard found.")

    try:
        storyboard = json.loads(project.script)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("Invalid storyboard JSON.")

    if not isinstance(storyboard, dict):
        raise ValueError("Invalid storyboard format.")

    if not isinstance(storyboard.get("scenes"), list):
        raise ValueError("Storyboard scenes are invalid.")

    return storyboard


def scene_to_dict(scene):
    """Convert a database scene into storyboard-compatible data."""

    return {
        "scene_number": scene.scene_number,
        "narration": scene.narration,
        "visual_description": scene.visual_description,
        "duration": scene.duration,
        "camera_motion": scene.camera_motion,
        "visual_type": scene.visual_type
    }


def sync_storyboard_scenes(project, scenes):
    """Synchronize the storyboard JSON with database scenes."""

    storyboard = load_storyboard(project)

    storyboard["scenes"] = [
        scene_to_dict(scene)
        for scene in scenes
    ]

    project.script = json.dumps(storyboard)


def renumber_scenes(scenes):
    """
    Renumber scenes safely while respecting the unique constraint.

    Temporary negative numbers prevent collisions when changing
    scene numbers in an existing database.
    """

    for index, scene in enumerate(scenes, start=1):
        scene.scene_number = -index

    db.session.flush()

    for index, scene in enumerate(scenes, start=1):
        scene.scene_number = index

    db.session.flush()


# ---------------------------------------------------------
# Create project
# ---------------------------------------------------------

@projects.route("", methods=["POST"])
@login_required
def create_project():

    data = request.get_json(silent=True) or {}

    title = data.get("title", "")
    topic = data.get("topic", "")

    if not isinstance(title, str) or not isinstance(topic, str):
        return jsonify({
            "error": "Title and topic must be text."
        }), 400

    title = title.strip()
    topic = topic.strip()

    if not title or not topic:
        return jsonify({
            "error": "Title and topic are required."
        }), 400

    project = Project(
        title=title,
        topic=topic,
        user_id=current_user.id
    )

    db.session.add(project)
    db.session.commit()

    return jsonify({
        "message": "Project created successfully",
        "project": {
            "id": project.id,
            "title": project.title,
            "topic": project.topic,
            "status": project.status
        }
    }), 201


# ---------------------------------------------------------
# Get projects
# ---------------------------------------------------------

@projects.route("", methods=["GET"])
@login_required
def get_projects():

    user_projects = Project.query.filter_by(
        user_id=current_user.id
    ).all()

    return jsonify([
        {
            "id": project.id,
            "title": project.title,
            "topic": project.topic,
            "status": project.status
        }
        for project in user_projects
    ]), 200


# ---------------------------------------------------------
# Update project
# ---------------------------------------------------------

@projects.route("/<int:project_id>", methods=["PUT"])
@login_required
def update_project(project_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    data = request.get_json(silent=True) or {}

    title = data.get("title")
    topic = data.get("topic")

    if title is not None:
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "Invalid title"}), 400

        project.title = title.strip()

    if topic is not None:
        if not isinstance(topic, str) or not topic.strip():
            return jsonify({"error": "Invalid topic"}), 400

        project.topic = topic.strip()

    db.session.commit()

    return jsonify({
        "message": "Project updated successfully",
        "project": {
            "id": project.id,
            "title": project.title,
            "topic": project.topic,
            "status": project.status
        }
    }), 200


# ---------------------------------------------------------
# Delete project
# ---------------------------------------------------------

@projects.route("/<int:project_id>", methods=["DELETE"])
@login_required
def delete_project(project_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    db.session.delete(project)
    db.session.commit()

    return jsonify({
        "message": "Project deleted successfully"
    }), 200


# ---------------------------------------------------------
# Generate storyboard
# ---------------------------------------------------------

@projects.route("/<int:project_id>/generate-script", methods=["POST"])
@login_required
def generate_project_script(project_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    try:
        storyboard = generate_script(project.topic)

        scenes_data = storyboard.get("scenes", [])

        if not scenes_data:
            raise ValueError(
                "Generated storyboard contains no scenes."
            )

        # Validate scene numbers before saving.
        new_scenes = []

        for index, scene_data in enumerate(scenes_data, start=1):

            scene_number = scene_data.get("scene_number", index)

            if (
                not isinstance(scene_number, int)
                or isinstance(scene_number, bool)
                or scene_number < 1
            ):
                raise ValueError("Invalid scene number.")

            narration = scene_data.get("narration")
            visual_description = scene_data.get("visual_description")

            if (
                not isinstance(narration, str)
                or not narration.strip()
                or not isinstance(visual_description, str)
                or not visual_description.strip()
            ):
                raise ValueError(
                    f"Scene {scene_number} has invalid narration or visuals."
                )

            visual_type = scene_data.get(
                "visual_type",
                "stock_video"
            )

            camera_motion = scene_data.get(
                "camera_motion",
                "none"
            )

            if visual_type not in ALLOWED_VISUAL_TYPES:
                raise ValueError(
                    f"Invalid visual type in scene {scene_number}."
                )

            if camera_motion not in ALLOWED_MOTIONS:
                raise ValueError(
                    f"Invalid camera motion in scene {scene_number}."
                )

            duration = float(scene_data.get("duration", 5))

            if not 1 <= duration <= 30:
                raise ValueError(
                    f"Invalid duration in scene {scene_number}."
                )

            scene_data["scene_number"] = scene_number
            scene_data["narration"] = narration.strip()
            scene_data["visual_description"] = visual_description.strip()
            scene_data["duration"] = duration
            scene_data["visual_type"] = visual_type
            scene_data["camera_motion"] = camera_motion

            new_scenes.append(
                Scene(
                    project_id=project.id,
                    scene_number=scene_number,
                    narration=narration.strip(),
                    visual_description=visual_description.strip(),
                    visual_type=visual_type,
                    duration=duration,
                    camera_motion=camera_motion,
                    status="pending"
                )
            )

        scene_numbers = [
            scene.scene_number
            for scene in new_scenes
        ]

        if len(scene_numbers) != len(set(scene_numbers)):
            raise ValueError("Duplicate scene numbers detected.")

        new_scenes.sort(key=lambda scene: scene.scene_number)

        # Replace existing database scenes.
        Scene.query.filter_by(
            project_id=project.id
        ).delete(synchronize_session=False)

        db.session.flush()

        storyboard["scenes"] = [
            scene_to_dict(scene)
            for scene in new_scenes
        ]

        project.script = json.dumps(storyboard)

        db.session.add_all(new_scenes)
        db.session.commit()

        return jsonify({
            "message": "Storyboard generated successfully",
            "project_id": project.id,
            "storyboard": storyboard,
            "scene_count": len(new_scenes)
        }), 200

    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Storyboard generation failed for project %s",
            project_id
        )

        return jsonify({
            "error": "Storyboard generation failed. Check the Flask terminal."
        }), 502


# ---------------------------------------------------------
# Generate video
# ---------------------------------------------------------

@projects.route("/<int:project_id>/generate", methods=["POST"])
@login_required
def generate_project(project_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    active_job = GenerationJob.query.filter_by(
        project_id=project_id,
        status="processing"
    ).first()

    if active_job:
        return jsonify({
            "error": "A generation job is already running.",
            "job_id": active_job.id,
            "status": active_job.status
        }), 409

    try:
        result = generate_project_video(project_id)

        return jsonify({
            "message": "Video generated successfully.",
            "result": result
        }), 200

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    except Exception:
        current_app.logger.exception(
            "Video generation failed for project %s",
            project_id
        )

        return jsonify({
            "error": "Video generation failed. Check the generation job for details."
        }), 500


# ---------------------------------------------------------
# Update individual scene
# ---------------------------------------------------------

@projects.route(
    "/<int:project_id>/scenes/<int:scene_id>",
    methods=["PUT"]
)
@login_required
def update_scene(project_id, scene_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    scene = Scene.query.filter_by(
        id=scene_id,
        project_id=project_id
    ).first()

    if not scene:
        return jsonify({"error": "Scene not found"}), 404

    data = request.get_json(silent=True) or {}

    narration = data.get("narration")
    visual_description = data.get("visual_description")
    duration = data.get("duration")
    camera_motion = data.get("camera_motion")
    visual_type = data.get("visual_type")

    if narration is not None:
        if not isinstance(narration, str) or not narration.strip():
            return jsonify({
                "error": "Narration cannot be empty"
            }), 400

        scene.narration = narration.strip()

    if visual_description is not None:
        if (
            not isinstance(visual_description, str)
            or not visual_description.strip()
        ):
            return jsonify({
                "error": "Visual description cannot be empty"
            }), 400

        scene.visual_description = visual_description.strip()

    if duration is not None:
        try:
            duration = float(duration)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid duration"}), 400

        if not 1 <= duration <= 30:
            return jsonify({
                "error": "Duration must be between 1 and 30 seconds"
            }), 400

        scene.duration = duration

    if camera_motion is not None:
        if camera_motion not in ALLOWED_MOTIONS:
            return jsonify({
                "error": "Invalid camera movement"
            }), 400

        scene.camera_motion = camera_motion

    if visual_type is not None:
        if visual_type not in ALLOWED_VISUAL_TYPES:
            return jsonify({
                "error": "Invalid visual type"
            }), 400

        scene.visual_type = visual_type

    try:
        scenes = (
            Scene.query
            .filter_by(project_id=project_id)
            .order_by(Scene.scene_number)
            .all()
        )

        sync_storyboard_scenes(project, scenes)

        db.session.commit()

        return jsonify({
            "message": "Scene updated successfully",
            "scene": {
                "id": scene.id,
                **scene_to_dict(scene)
            }
        }), 200

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Scene update failed for scene %s",
            scene_id
        )

        return jsonify({
            "error": "Could not update scene."
        }), 500


# ---------------------------------------------------------
# Add scene
# ---------------------------------------------------------

@projects.route(
    "/<int:project_id>/scenes",
    methods=["POST"]
)
@login_required
def add_scene(project_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    data = request.get_json(silent=True) or {}

    narration = data.get("narration", "")
    visual_description = data.get("visual_description", "")

    if not isinstance(narration, str) or not narration.strip():
        return jsonify({
            "error": "Narration is required."
        }), 400

    if (
        not isinstance(visual_description, str)
        or not visual_description.strip()
    ):
        return jsonify({
            "error": "Visual description is required."
        }), 400

    try:
        duration = float(data.get("duration", 5))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid duration."}), 400

    if not 1 <= duration <= 30:
        return jsonify({
            "error": "Duration must be between 1 and 30 seconds."
        }), 400

    camera_motion = data.get("camera_motion", "none")
    visual_type = data.get("visual_type", "stock_video")

    if camera_motion not in ALLOWED_MOTIONS:
        return jsonify({"error": "Invalid camera movement."}), 400

    if visual_type not in ALLOWED_VISUAL_TYPES:
        return jsonify({"error": "Invalid visual type."}), 400

    try:
        storyboard = load_storyboard(project)

        existing_scenes = (
            Scene.query
            .filter_by(project_id=project_id)
            .order_by(Scene.scene_number)
            .all()
        )

        scene_number = max(
            (scene.scene_number for scene in existing_scenes),
            default=0
        ) + 1

        scene = Scene(
            project_id=project_id,
            scene_number=scene_number,
            narration=narration.strip(),
            visual_description=visual_description.strip(),
            duration=duration,
            camera_motion=camera_motion,
            visual_type=visual_type,
            status="pending"
        )

        db.session.add(scene)
        db.session.flush()

        existing_scenes.append(scene)

        sync_storyboard_scenes(project, existing_scenes)

        db.session.commit()

        return jsonify({
            "message": "Scene added successfully.",
            "scene": {
                "id": scene.id,
                **scene_to_dict(scene)
            }
        }), 201

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Scene creation failed for project %s",
            project_id
        )

        return jsonify({
            "error": "Could not add scene."
        }), 500


# ---------------------------------------------------------
# Delete scene
# ---------------------------------------------------------

@projects.route(
    "/<int:project_id>/scenes/<int:scene_id>",
    methods=["DELETE"]
)
@login_required
def delete_scene(project_id, scene_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    scene = Scene.query.filter_by(
        id=scene_id,
        project_id=project_id
    ).first()

    if not scene:
        return jsonify({"error": "Scene not found"}), 404

    try:
        scenes = (
            Scene.query
            .filter_by(project_id=project_id)
            .order_by(Scene.scene_number)
            .all()
        )

        scenes.remove(scene)

        db.session.delete(scene)
        db.session.flush()

        # Renumber remaining scenes.
        renumber_scenes(scenes)

        # Keep the saved storyboard synchronized.
        sync_storyboard_scenes(project, scenes)

        db.session.commit()

        return jsonify({
            "message": "Scene deleted successfully.",
            "remaining_scene_count": len(scenes),
            "scenes": [
                {
                    "id": item.id,
                    **scene_to_dict(item)
                }
                for item in scenes
            ]
        }), 200

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Scene deletion failed for scene %s",
            scene_id
        )

        return jsonify({
            "error": "Could not delete scene."
        }), 500


# ---------------------------------------------------------
# Reorder scenes
# ---------------------------------------------------------

@projects.route(
    "/<int:project_id>/scenes/reorder",
    methods=["PUT"]
)
@login_required
def reorder_scenes(project_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    data = request.get_json(silent=True) or {}
    scene_ids = data.get("scene_ids")

    if not isinstance(scene_ids, list) or not scene_ids:
        return jsonify({
            "error": "A non-empty scene_ids list is required."
        }), 400

    if any(
        not isinstance(scene_id, int) or isinstance(scene_id, bool)
        for scene_id in scene_ids
    ):
        return jsonify({
            "error": "All scene IDs must be integers."
        }), 400

    if len(scene_ids) != len(set(scene_ids)):
        return jsonify({
            "error": "Duplicate scene IDs are not allowed."
        }), 400

    try:
        scenes = (
            Scene.query
            .filter_by(project_id=project_id)
            .all()
        )

        existing_ids = {
            scene.id
            for scene in scenes
        }

        if set(scene_ids) != existing_ids:
            return jsonify({
                "error": "The submitted scene IDs must include every scene exactly once."
            }), 400

        scene_by_id = {
            scene.id: scene
            for scene in scenes
        }

        ordered_scenes = [
            scene_by_id[scene_id]
            for scene_id in scene_ids
        ]

        # Change numbering without violating the unique constraint.
        renumber_scenes(ordered_scenes)

        sync_storyboard_scenes(project, ordered_scenes)

        db.session.commit()

        return jsonify({
            "message": "Scenes reordered successfully.",
            "scenes": [
                {
                    "id": scene.id,
                    **scene_to_dict(scene)
                }
                for scene in ordered_scenes
            ]
        }), 200

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Scene reordering failed for project %s",
            project_id
        )

        return jsonify({
            "error": "Could not reorder scenes."
        }), 500


# ---------------------------------------------------------
# Update storyboard hook and ending
# ---------------------------------------------------------

@projects.route(
    "/<int:project_id>/storyboard",
    methods=["PUT"]
)
@login_required
def update_storyboard_text(project_id):

    project = get_owned_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    data = request.get_json(silent=True) or {}

    hook = data.get("hook")
    ending = data.get("ending")

    if hook is None and ending is None:
        return jsonify({"error": "Nothing to update"}), 400

    if hook is not None:
        if not isinstance(hook, str) or not hook.strip():
            return jsonify({"error": "Hook cannot be empty"}), 400

    if ending is not None:
        if not isinstance(ending, str) or not ending.strip():
            return jsonify({"error": "Ending cannot be empty"}), 400

    try:
        storyboard = load_storyboard(project)

        if hook is not None:
            storyboard["hook"] = hook.strip()

        if ending is not None:
            storyboard["ending"] = ending.strip()

        project.script = json.dumps(storyboard)

        db.session.commit()

        return jsonify({
            "message": "Storyboard updated successfully",
            "hook": storyboard.get("hook", ""),
            "ending": storyboard.get("ending", "")
        }), 200

    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Storyboard update failed for project %s",
            project_id
        )

        return jsonify({
            "error": "Could not save storyboard."
        }), 500
