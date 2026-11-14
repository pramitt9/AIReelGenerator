
import os

from flask import (
    Blueprint,
    render_template,
    send_file,
    abort
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.models import Project, GenerationJob

main = Blueprint("main", __name__)


@main.route("/")
@login_required
def home():
    projects = (
        Project.query
        .filter_by(user_id=current_user.id)
        .order_by(Project.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template("index.html", projects=projects)


@main.route("/create")
@login_required
def create_page():
    return render_template("create.html")


@main.route("/gallery")
@login_required
def gallery():
    projects = (
        Project.query
        .filter_by(user_id=current_user.id)
        .order_by(Project.created_at.desc())
        .all()
    )

    return render_template("gallery.html", projects=projects)


@main.route("/projects/<int:project_id>/storyboard")
@login_required
def storyboard_page(project_id):
    project = Project.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    return render_template(
        "storyboard.html",
        project=project
    )


def get_completed_video(project_id):
    project = Project.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    job = (
        GenerationJob.query
        .filter_by(
            project_id=project.id,
            status="completed"
        )
        .order_by(GenerationJob.completed_at.desc())
        .first()
    )

    if not job or not job.output_video:
        abort(404, description="No completed video found.")

    if not os.path.isfile(job.output_video):
        abort(404, description="Generated video file is missing.")

    return job


@main.route("/projects/<int:project_id>/video")
@login_required
def preview_video(project_id):
    job = get_completed_video(project_id)

    return send_file(
        job.output_video,
        mimetype="video/mp4",
        as_attachment=False
    )


@main.route("/projects/<int:project_id>/download")
@login_required
def download_video(project_id):
    job = get_completed_video(project_id)

    project = Project.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    filename = secure_filename(project.title) or "vidsnapai_reel"

    return send_file(
        job.output_video,
        mimetype="video/mp4",
        as_attachment=True,
        download_name=f"{filename}.mp4"
    )
