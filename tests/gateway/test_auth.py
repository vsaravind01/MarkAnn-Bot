async def test_register_trader(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "trader@example.com",
            "password": "password123",
            "first_name": "Arjun",
            "last_name": "Sharma",
        },
    )
    assert response.status_code == 200
    assert response.json()["role"] == "trader"
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


async def test_register_duplicate_email_returns_409(client):
    payload = {
        "email": "dup@example.com",
        "password": "password123",
        "first_name": "A",
        "last_name": "B",
    }
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 409


async def test_register_invalid_email_returns_422(client):
    response = await client.post(
        "/auth/register",
        json={"email": "banana", "password": "password123", "first_name": "A", "last_name": "B"},
    )
    assert response.status_code == 422


async def test_register_short_password_returns_422(client):
    response = await client.post(
        "/auth/register",
        json={"email": "t@e.com", "password": "short", "first_name": "A", "last_name": "B"},
    )
    assert response.status_code == 422


async def test_register_long_password_returns_422(client):
    response = await client.post(
        "/auth/register",
        json={
            "email": "long@e.com",
            "password": "x" * 73,
            "first_name": "A",
            "last_name": "B",
        },
    )
    assert response.status_code == 422


async def test_login(client):
    await client.post(
        "/auth/register",
        json={"email": "t@e.com", "password": "password123", "first_name": "A", "last_name": "B"},
    )
    response = await client.post(
        "/auth/login", json={"email": "t@e.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies


async def test_login_wrong_password_returns_401(client):
    await client.post(
        "/auth/register",
        json={"email": "t@e.com", "password": "password123", "first_name": "A", "last_name": "B"},
    )
    response = await client.post("/auth/login", json={"email": "t@e.com", "password": "wrong"})
    assert response.status_code == 401


async def test_me_returns_current_user(client):
    await client.post(
        "/auth/register",
        json={
            "email": "t@e.com",
            "password": "password123",
            "first_name": "Arjun",
            "last_name": "Sharma",
        },
    )
    response = await client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "t@e.com"
    assert data["first_name"] == "Arjun"
    assert "password_hash" not in data


async def test_me_without_auth_returns_401(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_refresh_rotates_cookie(client):
    await client.post(
        "/auth/register",
        json={"email": "t@e.com", "password": "password123", "first_name": "A", "last_name": "B"},
    )
    old_refresh = client.cookies.get("refresh_token")
    response = await client.post("/auth/refresh")
    assert response.status_code == 200
    assert client.cookies.get("refresh_token") != old_refresh
    set_cookie = ",".join(response.headers.get_list("set-cookie"))
    assert "Path=/auth/refresh" in set_cookie


async def test_logout_clears_cookies(client):
    await client.post(
        "/auth/register",
        json={"email": "t@e.com", "password": "password123", "first_name": "A", "last_name": "B"},
    )
    response = await client.post("/auth/logout")
    assert response.status_code == 200


async def test_refresh_token_reuse_detected_at_http_layer(client):
    await client.post(
        "/auth/register",
        json={"email": "t@e.com", "password": "password123", "first_name": "A", "last_name": "B"},
    )
    stolen_refresh = client.cookies.get("refresh_token")

    first = await client.post("/auth/refresh")
    assert first.status_code == 200

    rotated_refresh = client.cookies.get("refresh_token")
    client.cookies.set("refresh_token", stolen_refresh, path="/auth/refresh")
    replay = await client.post("/auth/refresh")
    client.cookies.set("refresh_token", rotated_refresh, path="/auth/refresh")
    assert replay.status_code == 401
    assert "reuse" in replay.json()["detail"].lower()
