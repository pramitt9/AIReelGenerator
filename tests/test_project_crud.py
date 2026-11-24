import pytest

from app import create_app
from app.extensions import db
from app.models import User, Project


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-key",
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_project_crud(client, app):
    # Register. Registration automatically logs the user in.
    response = client.post("/register", data={
        "username": "cruduser",
        "email": "cruduser@example.com",
        "password": "password123",
        "confirm_password": "password123",
    }, follow_redirects=True)

    assert response.status_code == 200

    # Create project
    response = client.post("/api/projects", json={
        "title": "Original Title",
        "topic": "Artificial Intelligence",
    })

    assert response.status_code == 201
    project_id = response.get_json()["project"]["id"]

    # Read projects
    response = client.get("/api/projects")

    assert response.status_code == 200
    assert len(response.get_json()) == 1

    # Update project
    response = client.put(
        f"/api/projects/{project_id}",
        json={"title": "Updated Title"},
    )

    assert response.status_code == 200
    assert response.get_json()["project"]["title"] == "Updated Title"

    # Delete project
    response = client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 200

    with app.app_context():
        assert db.session.get(Project, project_id) is None
