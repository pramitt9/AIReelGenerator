import pytest

from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-key"
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_user_creation_and_password(app):
    with app.app_context():
        user = User(
            username="testuser",
            email="test@example.com"
        )

        user.set_password("testpassword123")

        db.session.add(user)
        db.session.commit()

        saved_user = User.query.filter_by(
            email="test@example.com"
        ).first()

        assert saved_user is not None
        assert saved_user.username == "testuser"
        assert saved_user.check_password("testpassword123")
        assert not saved_user.check_password("wrongpassword")
