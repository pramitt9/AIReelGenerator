from datetime import datetime, timezone

from app.extensions import db


class GenerationJob(db.Model):
    __tablename__ = "generation_jobs"

    id = db.Column(db.Integer, primary_key=True)

    status = db.Column(
        db.String(30),
        default="pending",
        nullable=False
    )

    progress = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    error_message = db.Column(db.Text, nullable=True)

    output_video = db.Column(db.String(500), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    completed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id"),
        nullable=False
    )

    project = db.relationship(
        "Project",
        back_populates="generation_jobs"
    )

    def __repr__(self):
        return f"<GenerationJob {self.id}: {self.status}>"