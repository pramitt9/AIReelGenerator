from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from flask_login import UserMixin


class User(UserMixin,db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(
        db.String(256),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    projects=db.relationship(
        "Project",back_populates="user", cascade="all,delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"

from app.extensions import login_manager

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User,int(user_id))