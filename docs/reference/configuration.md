# Configuration

All configuration is via environment variables, loaded from `.env` (gitignored — **never commit real secrets**). Copy `.env.example` to start.

## Auth (gateway)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `JWT_SECRET` | **yes** | — | Signs access-token JWTs. Generate: `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `HTTPS` | no | `false` | When `true`, auth cookies get the `secure` flag (production). |
| `ALLOWED_ORIGINS` | no | `http://localhost:5173` | CORS allow-list for the frontend origin. |
| `TRUSTED_GATEWAY_SECRET` | no | — | Optional shared secret the gateway adds as `x-gateway-secret` so the backend can verify the request came from the gateway. |
| `BACKEND_URL` | no | `http://backend:1530` | Where the gateway proxies to. |

## LLM (engine)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `LLM_PROVIDER` | **yes** (engine) | `openai` | `gemini` · `openai` · `anthropic`. |
| `GEMINI_API_KEY` | if gemini | — | Gemini key. |
| `GEMINI_MODEL` | no | provider default | Override the Gemini model. |
| `OPENAI_API_KEY` | if openai | — | OpenAI key (use a placeholder for local servers). |
| `OPENAI_BASE_URL` | no | — | OpenAI-compatible endpoint, e.g. `http://host.docker.internal:8000/v1` for local vLLM. |
| `OPENAI_MODEL` | no | provider default | Override the OpenAI/compatible model. |
| `ANTHROPIC_API_KEY` | if anthropic | — | Anthropic key. |

See [LLM providers](../guides/llm-providers.md) for how these interact and the local-server setup.

## Infrastructure

| Variable | Default (Compose) | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://markann:markann@postgres:5432/markann` | Async SQLAlchemy connection string. |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string. |

For local (non-Compose) runs, point these at `localhost`.

## Engine tuning

| Variable | Default | Purpose |
|---|---|---|
| `POLL_INTERVAL` | `5` | Baseline seconds between NSE polls. |
| `POLLER_SILENCE_THRESHOLD` | `600` | Seconds a poller may run without producing data before the watchdog logs a silence alarm. |

## Per-component config (not env)

Some tuning lives in the [registry](../architecture/registry.md), not the environment, because it's per-component and operator-editable at runtime:

| Config key | Component | Set via |
|---|---|---|
| `base_interval` | poller | registry `config` (module default) |
| `pool_size` | processor | Processors page resize → `PATCH /admin/processors/{api}` |

## Minimal `.env`

```bash
# Auth
JWT_SECRET=<64 hex chars>

# LLM
LLM_PROVIDER=gemini
GEMINI_API_KEY=<your key>

# Engine
POLL_INTERVAL=5
```

The Compose file supplies the database and Redis URLs between containers, so those two blocks are all a fresh stack needs.

## Precedence & safety

- `.env` is read by Docker Compose and by local `uv run` invocations.
- **`.env` and any real key must never be committed** — it's gitignored for that reason.
- Compose namespaces data volumes by directory name; see the [volume note](../operations/deployment.md#per-directory-volume-names).
