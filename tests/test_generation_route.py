
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import User, Project


app = create_app({
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False
})


def test_generation_route():
    with app.app_context():
        db.create_all()

        try:
            user = User(
                username="generation_route_test",
                email="generation_route_test@example.com"
            )
            user.set_password("testpassword123")

            db.session.add(user)
            db.session.commit()

            project = Project(
                title="Generation Route Test",
                topic="Artificial Intelligence",
                user_id=user.id
            )

            db.session.add(project)
            db.session.commit()

            project_id = project.id

            client = app.test_client()

            # Login
            login_response = client.post(
                "/login",
                data={
                    "email": "generation_route_test@example.com",
                    "password": "testpassword123"
                },
                follow_redirects=True
            )

            print("Login status:", login_response.status_code)
            print("Login URL:", login_response.request.path)
            print("Login response:", login_response.get_data(as_text=True)[:1000])

            assert login_response.status_code == 200

            mock_result = {
                "job_id": 999,
                "project_id": project_id,
                "status": "completed",
                "output_video": "mock_final_reel.mp4"
            }

            with patch(
                "app.routes.projects.generate_project_video",
                return_value=mock_result
            ) as mock_pipeline:

                response = client.post(
                    f"/api/projects/{project_id}/generate"
                )

                print("HTTP status:", response.status_code)
                print("Response:", response.json)

                assert response.status_code == 200
                assert response.json["result"]["status"] == "completed"

                mock_pipeline.assert_called_once_with(project_id)

            print("\nGeneration API route test passed!")

        finally:
            db.session.rollback()
            db.drop_all()
            db.session.remove()

