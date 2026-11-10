from app import create_app
from unittest.mock import patch

app = create_app()
app.config["TESTING"] = True

client = app.test_client()

# Register and login
client.post(
    "/auth/register",
    json={
        "username": "cruduser",
        "email": "cruduser@example.com",
        "password": "password123"
    }
)

client.post(
    "/auth/login",
    json={
        "email": "cruduser@example.com",
        "password": "password123"
    }
)

# Create
response = client.post(
    "/api/projects",
    json={
        "title": "Original Title",
        "topic": "Artificial Intelligence"
    }
)

project_id = response.json["project"]["id"]
print("Create:", response.status_code)

mock_storyboard = {
    "title": "The Future of AI",
    "hook": "AI is changing everything.",
    "scenes": [
        {
            "scene_number": 1,
            "narration": "Artificial intelligence is evolving rapidly.",
            "visual_description": "A futuristic city with AI technology.",
            "visual_type": "stock_video",
            "duration": 5
        }
    ],
    "ending": "The future is already here."
}

with patch(
    "app.routes.projects.generate_script",
    return_value=mock_storyboard
):
    response = client.post(
        f"/api/projects/{project_id}/generate-script"
    )

print("Generate script:", response.status_code)
print(response.json)

# Update
response = client.put(
    f"/api/projects/{project_id}",
    json={"title": "Updated Title"}
)

print("Update:", response.status_code)
print(response.json)

# Delete
response = client.delete(
    f"/api/projects/{project_id}"
)

print("Delete:", response.status_code)
print(response.json)

# Verify deletion
response = client.get("/api/projects")

print("Remaining projects:", response.json)