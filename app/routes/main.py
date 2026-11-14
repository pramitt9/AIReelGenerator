
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Project

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
    from app.models import Project

    project = Project.query.filter_by(
        id=project_id,
        user_id=current_user.id
    ).first_or_404()

    return render_template(
        "storyboard.html",
        project=project
    )