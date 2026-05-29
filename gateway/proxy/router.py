from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from gateway.auth.deps import get_current_user
from gateway.proxy.client import get_client

router = APIRouter(tags=["proxy"])

_ROUTE_ROLES: list[tuple[str, frozenset[str]]] = [
    ("/admin/", frozenset({"admin", "superuser"})),
    ("/api/v1/", frozenset({"trader", "admin", "superuser"})),
]


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request) -> Response:
    user = await get_current_user(request)
    full_path = f"/{path}"

    allowed_roles: frozenset[str] | None = None
    for prefix, roles in _ROUTE_ROLES:
        if full_path.startswith(prefix):
            allowed_roles = roles
            break

    if allowed_roles is None:
        raise HTTPException(status_code=404, detail="Not found")
    if user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    settings = request.app.state.settings
    target = settings.backend_url.rstrip("/") + full_path
    if request.url.query:
        target += f"?{request.url.query}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"cookie", "host"}
    }
    headers["x-user-id"] = str(user.id)
    headers["x-user-role"] = user.role
    if settings.trusted_gateway_secret:
        headers["x-gateway-secret"] = settings.trusted_gateway_secret

    body = await request.body()
    client = get_client()

    try:
        backend_response = await client.request(
            method=request.method,
            url=target,
            headers=headers,
            content=body,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Backend unavailable") from exc

    excluded_headers = {"transfer-encoding", "content-encoding", "set-cookie"}
    response_headers = {
        key: value
        for key, value in backend_response.headers.items()
        if key.lower() not in excluded_headers
    }

    return Response(
        content=backend_response.content,
        status_code=backend_response.status_code,
        headers=response_headers,
        media_type=backend_response.headers.get("content-type"),
    )
