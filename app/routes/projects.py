from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import json
from app.services.ai.script_generator import generate_script

from app.extensions import db
from app.models import Project

projects = Blueprint(
    "projects",
    __name__,
    url_prefix="/api/projects"
)


@projects.route("", methods=["POST"])
@login_required
def create_project():

    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    topic = data.get("topic", "").strip()

    if not title or not topic:
        return jsonify({
            "error": "Title and topic are required"
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


@projects.route("", methods=["GET"])
@login_required
def get_projects():

    user_projects = Project.query.filter_by(
        user_id=current_user.id
    ).all()

    return jsonify([
        {
            "id": p.id,
            "title": p.title,
            "topic": p.topic,
            "status": p.status
        }
        for p in user_projects
    ]), 200

@projects.route("/<int:project_id>", methods=["PUT"])
@login_required
def update_project(project_id):

    project = Project.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first()

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

@projects.route("/<int:project_id>", methods=["DELETE"])
@login_required
def delete_project(project_id):

    project = Project.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first()

    if not project:
        return jsonify({"error": "Project not found"}), 404

    db.session.delete(project)
    db.session.commit()

    return jsonify({
        "message": "Project deleted successfully"
    }), 200


@projects.route("/<int:project_id>/generate-script", methods=["POST"])
@login_required
def generate_project_script(project_id):

    project = Project.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first()

    if not project:
        return jsonify({"error": "Project not found"}), 404

    try:
        storyboard = generate_script(project.topic)

        # Save structured storyboard as JSON in the Text column
        project.script = json.dumps(storyboard)

        db.session.commit()

        return jsonify({
            "message": "Script generated successfully",
            "project_id": project.id,
            "storyboard": storyboard
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "Script generation failed. Please try again."
        }), 502
