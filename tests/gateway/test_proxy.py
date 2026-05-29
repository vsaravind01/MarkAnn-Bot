import httpx
import respx


async def _make_trader(client, email="trader@e.com"):
    await client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "first_name": "T", "last_name": "R"},
    )


async def _make_superuser(client):
    await client.post(
        "/auth/admin/register",
        json={
            "email": "super@e.com",
            "password": "password123",
            "first_name": "S",
            "last_name": "U",
        },
    )


@respx.mock
async def test_trader_can_access_api_v1(client):
    await _make_trader(client)
    respx.get("http://test-backend/api/v1/watchlist").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    response = await client.get("/api/v1/watchlist")
    assert response.status_code == 200


@respx.mock
async def test_trader_blocked_from_admin(client):
    await _make_trader(client)
    response = await client.get("/admin/pollers")
    assert response.status_code == 403


@respx.mock
async def test_superuser_can_access_admin(client):
    await _make_superuser(client)
    respx.get("http://test-backend/admin/pollers").mock(return_value=httpx.Response(200, json=[]))
    response = await client.get("/admin/pollers")
    assert response.status_code == 200


async def test_unauthenticated_request_returns_401(client):
    client.cookies.clear()
    response = await client.get("/api/v1/watchlist")
    assert response.status_code == 401


async def test_unknown_path_returns_404(client):
    await _make_trader(client)
    response = await client.get("/unknown/path")
    assert response.status_code == 404


@respx.mock
async def test_x_user_headers_injected(client):
    await _make_trader(client)
    captured_headers: dict[str, str] = {}

    def capture(request):
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json={})

    respx.get("http://test-backend/api/v1/watchlist").mock(side_effect=capture)
    await client.get("/api/v1/watchlist")

    assert "x-user-id" in captured_headers
    assert captured_headers["x-user-role"] == "trader"
    assert "cookie" not in captured_headers


@respx.mock
async def test_backend_set_cookie_not_forwarded(client):
    await _make_trader(client)
    respx.get("http://test-backend/api/v1/watchlist").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "bad=1; Path=/"}, json={})
    )
    response = await client.get("/api/v1/watchlist")
    assert response.status_code == 200
    assert "set-cookie" not in {k.lower() for k in response.headers}
