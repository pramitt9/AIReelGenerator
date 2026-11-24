from app import create_app

app = create_app()
app.config["TESTING"] = True

client = app.test_client()

# 1. Register a new user
response = client.post(
    "/auth/register",
    json={
        "username": "john",
        "email": "john@example.com",
        "password": "password123"
    }
)

print("Registration:", response.status_code)
print(response.json)


# 2. Login
response = client.post(
    "/auth/login",
    json={
        "email": "john@example.com",
        "password": "password123"
    }
)

print("\nLogin:", response.status_code)
print(response.json)


# 3. Access protected route
response = client.get("/auth/me")

print("\nCurrent user:", response.status_code)
print(response.json)


# 4. Logout
response = client.post("/auth/logout")

print("\nLogout:", response.status_code)
print(response.json)


# 5. Try accessing protected route again
response = client.get("/auth/me")

print("\nAfter logout:", response.status_code)