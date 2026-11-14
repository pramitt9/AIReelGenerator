
from datetime import datetime, timezone

from app.extensions import db


class Scene(db.Model):
    __tablename__ = "scenes"

    id = db.Column(db.Integer, primary_key=True)

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id"),
        nullable=False,
        index=True
    )

    scene_number = db.Column(db.Integer, nullable=False)

    narration = db.Column(db.Text, nullable=False)

    visual_description = db.Column(db.Text, nullable=False)

    visual_type = db.Column(
        db.String(30),
        default="stock_video",
        nullable=False
    )

    duration = db.Column(db.Float, nullable=False)

    camera_motion = db.Column(
        db.String(20),
        default="none",
        nullable=False
    )

    # Asset information
    provider = db.Column(db.String(50))
    provider_video_id = db.Column(db.String(100))
    asset_url = db.Column(db.Text)
    asset_path = db.Column(db.Text)
    thumbnail_url = db.Column(db.Text)

    # Video metadata
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)

    # Processing status
    status = db.Column(
        db.String(30),
        default="pending",
        nullable=False
    )

    error_message = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    project = db.relationship(
        "Project",
        back_populates="scenes"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "project_id",
            "scene_number",
            name="unique_project_scene"
        ),
    )

    def __repr__(self):
        return f"<Scene {self.scene_number} | Project {self.project_id}>"
