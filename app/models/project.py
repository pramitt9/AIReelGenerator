from datetime import datetime, timezone

from app.extensions import db


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(
        db.String(150),
        nullable=False
    )

    topic = db.Column(
        db.String(255),
        nullable=False
    )

    script = db.Column(
        db.Text,
        nullable=True
    )

    status = db.Column(
        db.String(30),
        default="draft",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    user = db.relationship(
        "User",
        back_populates="projects"
    )

    generation_jobs=db.relationship(
        "GenerationJob",
        back_populates="project",
        cascade="all,delete-orphan"
    )

    scenes = db.relationship(
    "Scene",
    back_populates="project",
    cascade="all, delete-orphan",
    order_by="Scene.scene_number"
    )

    def __repr__(self):
        return f"<Project {self.title}>"