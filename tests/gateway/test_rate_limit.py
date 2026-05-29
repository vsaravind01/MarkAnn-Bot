async def test_under_limit_passes(client):
    for _ in range(5):
        response = await client.post("/auth/login", json={"email": "x@x.com", "password": "wrong"})
        assert response.status_code != 429


async def test_over_limit_returns_429(client):
    for _ in range(10):
        await client.post("/auth/login", json={"email": "x@x.com", "password": "wrong"})
    response = await client.post("/auth/login", json={"email": "x@x.com", "password": "wrong"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert 1 <= int(response.headers["Retry-After"]) <= 60


async def test_non_rate_limited_route_not_affected(client):
    for _ in range(15):
        response = await client.get("/health")
        assert response.status_code == 200


async def test_xff_header_cannot_bypass_rate_limit(client):
    for i in range(10):
        await client.post(
            "/auth/login",
            json={"email": "x@x.com", "password": "wrong"},
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
        )
    response = await client.post(
        "/auth/login",
        json={"email": "x@x.com", "password": "wrong"},
        headers={"X-Forwarded-For": "192.0.2.100"},
    )
    assert response.status_code == 429


async def test_rate_limited_response_has_cors_headers(client):
    for _ in range(10):
        await client.post("/auth/login", json={"email": "x@x.com", "password": "wrong"})
    response = await client.post(
        "/auth/login",
        json={"email": "x@x.com", "password": "wrong"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 429
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
