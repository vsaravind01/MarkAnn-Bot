async def _register_superuser(client):
    response = await client.post(
        "/auth/admin/register",
        json={
            "email": "super@e.com",
            "password": "password123",
            "first_name": "Super",
            "last_name": "User",
        },
    )
    assert response.status_code == 200
    return response.json()


async def _register_trader(client, email="trader@e.com"):
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "first_name": "T", "last_name": "R"},
    )
    assert response.status_code == 200
    return response.json()


async def test_first_admin_register_becomes_superuser(client):
    data = await _register_superuser(client)
    assert data["role"] == "superuser"


async def test_second_admin_register_without_auth_returns_403(client):
    await _register_superuser(client)
    await client.post("/auth/logout")
    response = await client.post(
        "/auth/admin/register",
        json={
            "email": "admin2@e.com",
            "password": "password123",
            "first_name": "A",
            "last_name": "D",
        },
    )
    assert response.status_code == 403


async def test_superuser_can_create_admin(client):
    await _register_superuser(client)
    response = await client.post(
        "/auth/admin/register",
        json={
            "email": "admin2@e.com",
            "password": "password123",
            "first_name": "A",
            "last_name": "D",
        },
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    check = await client.get("/auth/admin/users")
    assert check.status_code == 200


async def test_list_all_users_requires_superuser(client):
    await _register_superuser(client)
    response = await client.get("/auth/admin/users")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_list_all_users_blocked_for_trader(client):
    await _register_superuser(client)
    await client.post("/auth/logout")
    await _register_trader(client)
    response = await client.get("/auth/admin/users")
    assert response.status_code == 403


async def test_list_traders(client):
    await _register_superuser(client)
    await _register_trader(client, "t1@e.com")
    await _register_trader(client, "t2@e.com")
    await client.post("/auth/login", json={"email": "super@e.com", "password": "password123"})
    response = await client.get("/auth/admin/traders")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(user["role"] == "trader" for user in data["items"])


async def test_patch_user_disable(client):
    await _register_superuser(client)
    await _register_trader(client, "trader@e.com")
    await client.post("/auth/login", json={"email": "super@e.com", "password": "password123"})

    users = await client.get("/auth/admin/traders")
    trader_id = users.json()["items"][0]["id"]
    response = await client.patch(f"/auth/admin/users/{trader_id}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_cannot_disable_superuser(client):
    await _register_superuser(client)
    me = await client.get("/auth/me")
    superuser_id = me.json()["id"]

    response = await client.patch(f"/auth/admin/users/{superuser_id}", json={"is_active": False})
    assert response.status_code == 422


async def test_patch_unknown_user_returns_404(client):
    await _register_superuser(client)
    response = await client.patch("/auth/admin/users/999999", json={"is_active": False})
    assert response.status_code == 404


async def test_patch_trader_by_admin_role(client):
    await _register_superuser(client)
    await client.post(
        "/auth/admin/register",
        json={
            "email": "admin2@e.com",
            "password": "password123",
            "first_name": "A",
            "last_name": "D",
        },
    )
    await _register_trader(client, "target@e.com")
    await client.post("/auth/login", json={"email": "admin2@e.com", "password": "password123"})

    traders = await client.get("/auth/admin/traders")
    trader_id = next(
        item["id"] for item in traders.json()["items"] if item["email"] == "target@e.com"
    )
    response = await client.patch(f"/auth/admin/traders/{trader_id}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_patch_trader_rejects_non_trader_target(client):
    await _register_superuser(client)
    await client.post(
        "/auth/admin/register",
        json={
            "email": "admin2@e.com",
            "password": "password123",
            "first_name": "A",
            "last_name": "D",
        },
    )
    await client.post("/auth/login", json={"email": "super@e.com", "password": "password123"})
    users = await client.get("/auth/admin/users")
    admin2_id = next(item["id"] for item in users.json()["items"] if item["email"] == "admin2@e.com")
    response = await client.patch(f"/auth/admin/traders/{admin2_id}", json={"is_active": False})
    assert response.status_code == 422
