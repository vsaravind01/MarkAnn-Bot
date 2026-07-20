# API endpoints

All client traffic goes through the **gateway** (`:9150`). The gateway serves auth and user-management routes itself and reverse-proxies `/admin/*` and `/api/v1/*` to the internal backend after checking the caller's role.

**Roles:** `trader` · `admin` · `superuser`.

- `/admin/*` → `admin`, `superuser`
- `/api/v1/*` → any authenticated user
- unmatched paths → `404`

Auth is cookie-based; see [Security](../architecture/security.md).

## Auth — `gateway/auth`

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/auth/register` | public | Self-register a trader. |
| `POST` | `/auth/login` | public | Log in; sets `access_token` + `refresh_token` cookies. |
| `POST` | `/auth/refresh` | refresh cookie | Rotate the access token. |
| `POST` | `/auth/logout` | cookie | Clear the session. |
| `GET` | `/auth/me` | authenticated | Current user. |

## User management — `gateway/admin`

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/auth/admin/register` | admin (bootstrap) | Create an admin/superuser. |
| `GET` | `/auth/admin/users` | admin | List all users. |
| `GET` | `/auth/admin/users/{user_id}` | admin | Fetch a user. |
| `PATCH` | `/auth/admin/users/{user_id}` | admin | Update a user. |
| `GET` | `/auth/admin/traders` | admin | List traders. |
| `PATCH` | `/auth/admin/traders/{user_id}` | admin | Update a trader. |

## Engine — pollers (`/admin/pollers`, proxied)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/pollers` | All pollers with health. |
| `GET` | `/admin/pollers/{api}` | One poller's health. |
| `POST` | `/admin/pollers/{api}/pause` | Pause. |
| `POST` | `/admin/pollers/{api}/resume` | Resume. |
| `POST` | `/admin/pollers/{api}/restart` | Force-restart. |

Health payload fields: `api`, `status`, `heartbeat`, `last_success`, `error_count`, `interval`.

## Engine — processors (`/admin/processors`, proxied)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/processors` | All processors with health + config. |
| `GET` | `/admin/processors/{api}` | One processor. |
| `PATCH` | `/admin/processors/{api}` | Resize the worker pool. Body: `{"pool_size": <1–64>}`. Applies on restart. |
| `POST` | `/admin/processors/{api}/pause` | Pause. |
| `POST` | `/admin/processors/{api}/resume` | Resume. |
| `POST` | `/admin/processors/{api}/restart` | Force-restart. |
| `GET` | `/admin/processor-poller-links` | Registry wiring (processor → poller[s]). |

Processor payload fields: `api`, `status`, `queue_size`, `module`, `enabled`, `config`, `pollers`.

## Engine — events (`/admin/events`, proxied)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/events` | Rolling engine event log (newest first). |

Event fields: `ts` (epoch seconds), `lvl` (`ok`/`info`/`warn`/`crit`), `msg`, optional `api`. See [Observability](../operations/observability.md#the-event-log).

## Watchlist — `/api/v1/watchlist` (proxied)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/watchlist` | authenticated | Subscribe a user to a symbol. |
| `DELETE` | `/api/v1/watchlist` | authenticated | Unsubscribe from a symbol. |

## Health

Both the gateway and the backend expose an unauthenticated `GET /health` returning `{"status": "ok"}` — used by the Compose healthchecks.

!!! tip "Interactive API docs"
    FastAPI serves auto-generated OpenAPI docs at `/docs` (Swagger UI) and `/redoc` on each app. In development, browse the gateway's at <http://localhost:9150/docs>.
