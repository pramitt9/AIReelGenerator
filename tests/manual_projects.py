from app import create_app

app = create_app()
app.config["TESTING"] = True

client = app.test_client()

# Register
client.post(
    "/auth/register",
    json={
        "username": "projectuser",
        "email": "projectuser@example.com",
        "password": "password123"
    }
)

# Login
client.post(
    "/auth/login",
    json={
        "email": "projectuser@example.com",
        "password": "password123"
    }
)

# Create project
response = client.post(
    "/api/projects",
    json={
        "title": "My First AI Reel",
        "topic": "The future of artificial intelligence"
    }
)

print("Create:", response.status_code)
print(response.json)

# Get projects
response = client.get("/api/projects")

print("\nList:", response.status_code)
print(response.json)

# Test unauthenticated access
client.post("/auth/logout")

response = client.get("/api/projects")

print("\nUnauthenticated access:", response.status_code)