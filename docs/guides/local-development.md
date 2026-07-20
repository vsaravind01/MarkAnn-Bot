# Local development

This page covers working on MarkAnn outside Docker — running services individually with hot-reload, and the lint/test loop. For a one-command stack, see [Deployment](../operations/deployment.md).

## Prerequisites

- **Python 3.13**
- **[UV](https://docs.astral.sh/uv/)** — the package manager
- **PostgreSQL** and **Redis** running locally
- **Node.js** (for the frontend)
- An LLM provider key (or a local vLLM server — see [LLM providers](llm-providers.md))

## First-time setup

```bash
git clone https://github.com/vsaravind01/MarkAnn-Bot.git
cd MarkAnn
uv sync                       # install all Python deps into .venv
cp .env.example .env          # then fill in JWT_SECRET and your LLM key
```

Point `DATABASE_URL` and `REDIS_URL` at your local instances:

```bash
DATABASE_URL=postgresql+asyncpg://markann:markann@localhost:5432/markann
REDIS_URL=redis://localhost:6379/0
```

Then migrate and seed:

```bash
alembic -c database/migrations/alembic.ini upgrade head    # create tables
uv run python -m engine.register seed                     # register + enable defaults
```

## Running the services

Each in its own terminal (all support hot-reload except the engine):

```bash
# Gateway — the public API (:9150)
uv run uvicorn gateway.main:app --port 9150 --reload

# Backend — internal API (:1530)
uv run uvicorn api.app:app --port 1530 --reload

# Engine — pollers + processors (no hot-reload)
uv run python -m engine.main

# Frontend — admin console (:5173)
cd app/admin && npm install && npm run dev
```

!!! warning "The engine does not hot-reload"
    `uvicorn --reload` restarts the gateway and backend on file changes, but `python -m engine.main` does not. After changing any engine, poller, or processor code, **restart the engine process** for it to take effect. This also applies to the running Compose `engine` container — `docker compose restart engine`.

Open the console at **http://localhost:5173** and create the first superuser on first run.

## The test loop

```bash
uv run pytest                    # backend suite — offline (fakeredis + in-memory SQLite)
uv run pytest -m integration     # optional — hits real external APIs (needs .env.test)
cd app/admin && npm test         # frontend — Vitest + Testing Library
```

The default backend suite excludes `integration`-marked tests (`addopts = "-m 'not integration'"` in `pyproject.toml`), so it needs **no running Redis or Postgres** — `fakeredis` and `aiosqlite` stand in.

## Lint & format

```bash
uv run ruff check .              # lint
uv run ruff format .             # format
cd app/admin && npm run lint     # frontend lint
```

Ruff is the source of truth for Python style (config in `pyproject.toml`: line length 100, rule sets `E,F,I,UP,B,SIM`). Run both before committing.

## Migrations

After changing a model in `database/models.py`:

```bash
alembic -c database/migrations/alembic.ini revision --autogenerate -m "describe the change"
alembic -c database/migrations/alembic.ini upgrade head
```

!!! tip "Single migration head"
    Alembic requires a single linear head. If you branch and both branches add a migration, re-chain one migration's `down_revision` onto the other after merging so there's one head. Check with `alembic -c database/migrations/alembic.ini heads`.

## Previewing the docs

The docs are MkDocs Material. Serve them with live reload:

```bash
uv run --group docs mkdocs serve
```

Then open <http://127.0.0.1:8000>. See [Deployment](../operations/deployment.md#publishing-the-docs) for how they publish to GitHub Pages.

## Project layout

| Path | What |
|---|---|
| `gateway/` | Public gateway: auth, RBAC, rate-limit, proxy |
| `api/` | Backend API: `admin/` + `v1/` routers |
| `engine/` | Engine: `pollers/`, `processors/`, supervisor, registry, session |
| `llm/` | Provider implementations + factory |
| `database/` | Models, async session, Redis keys, `migrations/` |
| `app/admin/` | React + TypeScript frontend |
| `tests/` | pytest suites mirroring the packages |
| `docs/` | This documentation |
