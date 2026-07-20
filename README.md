<div align="center">
  <img src="assets/avatar.png" alt="MarkAnn" width="160" height="160" style="border-radius: 12px;">
  <h1>MarkAnn</h1>
  <p><strong>Real-time, AI-powered market-alert platform for Indian stock markets (NSE)</strong></p>
  <p>
    <img alt="Python" src="https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white">
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white">
    <img alt="React" src="https://img.shields.io/badge/React-TS-61DAFB?logo=react&logoColor=black">
    <img alt="License" src="https://img.shields.io/badge/license-GPL--2.0-blue">
  </p>
</div>

---

MarkAnn watches NSE data streams, runs detection and AI analysis on what it finds, and delivers the results to users through configurable channels. It is built **API-first**: a gateway is the single public entrypoint, the backend API is the source of truth, an autonomous engine does the polling and processing, and a web console gives operators live control over the running system.

The first shipped feature is **AI-powered corporate announcements** — MarkAnn polls NSE press releases, reads the attached PDF (as images, with a text fallback), summarises and classifies it with an LLM, stores it, and publishes an alert to everyone watching that symbol.

<div align="center">
  <img src="docs/img/dashboard.png" alt="MarkAnn operations dashboard" width="880">
  <br>
  <em>The operations console — live poller &amp; processor health, with pause / resize / force-restart controls.</em>
</div>

## Table of contents

- [Highlights](#highlights)
- [Alert types](#alert-types)
- [Architecture](#architecture)
- [The corporate-announcements pipeline](#the-corporate-announcements-pipeline)
- [The component registry](#the-component-registry)
- [The admin console](#the-admin-console)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [API surface](#api-surface)
- [Testing](#testing)
- [Development](#development)
- [Roadmap](#roadmap)
- [Documentation](#documentation)
- [License](#license)

## Highlights

- **Gateway-fronted, RBAC-secured.** A single public gateway handles authentication (cookie-based JWT), role checks, and rate limiting, then reverse-proxies to an internal backend. The backend never faces the internet.
- **DB-driven component registry.** Pollers and processors are *rows in Postgres*, not hardcoded wiring. The engine loads only what is enabled, validates that a processor's input schema is compatible with its poller's output, and skips anything broken — all without a redeploy.
- **Live operational control.** Pause, resume, force-restart, and resize worker pools from the web console. Commands travel over a Redis control channel to the engine's supervisor in real time.
- **Self-healing engine.** A supervisor auto-restarts crashed tasks, a watchdog flags pollers that go silent, and a circuit breaker backs off failing data sources.
- **Multimodal LLM analysis.** Announcement PDFs are rendered to page images and read by a vision LLM, with automatic page-by-page continuation for long documents and a plain-text extraction fallback.
- **Provider-agnostic AI.** OpenAI, Anthropic, and Gemini are interchangeable via one env var — including OpenAI-compatible local servers (e.g. vLLM) for offline experimentation.

## Alert types

| Status | Alert |
|---|---|
| ✅ **Live** | **AI corporate announcements** — fetch NSE press releases → read PDF → summarise + classify → publish to subscribers |
| 🔜 Planned | Volume spike detection |
| 🔜 Planned | Price spike detection |
| 🔜 Planned | EMA crossover detection |
| 🔜 Planned | Resistance / Support level crossing |
| 🔜 Planned | Bollinger Band crossing |
| 🔜 Planned | Volume Point of Control (VPoC) spike |

New alert types are added incrementally as poller + processor pairs against the same registry contract — see [The component registry](#the-component-registry).

## Architecture

MarkAnn is four cooperating services plus Postgres and Redis. Only the gateway and the frontend are publicly exposed.

```
                            ┌──────────────────────────┐
   Browser ── cookie JWT ──▶│  Frontend (React/TS)     │  :5173
                            │  Admin operations console │
                            └────────────┬─────────────┘
                                         │  HTTP
                            ┌────────────▼─────────────┐
                            │  Gateway  (FastAPI)      │  :9150   ◀── the only public entrypoint
                            │  • auth: login/refresh   │
                            │  • RBAC by route prefix  │
                            │  • rate-limit middleware │
                            │  • reverse proxy         │
                            └────────────┬─────────────┘
                          injects x-user-id / x-user-role
                            ┌────────────▼─────────────┐
                            │  Backend API (FastAPI)   │  :1530   (internal only)
                            │  /admin/*  · /api/v1/*   │
                            └───────┬───────────┬──────┘
                                    │           │
                        ┌───────────▼──┐   ┌────▼───────────────────────────┐
                        │  PostgreSQL  │   │  Redis                         │
                        │  users,      │   │  queues · dedup · inflight     │
                        │  watchlist,  │   │  heartbeats · status · events  │
                        │  announcements│  │  pub/sub · engine:control      │
                        │  registry    │   └────┬──────────────────────▲────┘
                        └───────▲──────┘        │  BLPOP / RPUSH       │ control
                                │               │                      │
                        ┌───────┴───────────────▼──────────────────────┴────┐
                        │  Engine  (python -m engine.main)                   │
                        │  Registry → Supervisor → Watchdog                  │
                        │  Pollers ─fetch─▶ NSE API ─▶ queue:{api}           │
                        │  Processors (ConsumerPool) ─▶ LLM ─▶ DB + alerts   │
                        └────────────────────────────────────────────────────┘
```

**Responsibilities**

| Service | Role |
|---|---|
| **Gateway** (`gateway/`) | The front door. Issues and validates JWTs (stored as `httponly`, `samesite=strict` cookies), enforces role-based access by URL prefix, rate-limits, and proxies allowed requests to the backend with trusted `x-user-*` headers. |
| **Backend API** (`api/`) | Source of truth. Serves `/admin/*` (poller/processor health + control, event log) and `/api/v1/*` (watchlist). Trusts the gateway's identity headers. |
| **Engine** (`engine/`) | The autonomous worker. Loads enabled components from the registry, runs pollers against NSE, and drains the work queues through processor pools. Hosts the supervisor, watchdog, and circuit breaker. |
| **Frontend** (`app/admin/`) | React + TypeScript operations console. The primary human interface for monitoring and controlling the engine. |
| **PostgreSQL** | Durable state: users & auth, watchlists, channels, processed announcements, and the component registry. |
| **Redis** | The nervous system: work queues, two-level dedup, poller heartbeats/status, the rolling event log, alert pub/sub, and the `engine:control` command channel. |

**Engine internals**

- **`Supervisor`** — registers each component as `poller:{api}` / `processor:{api}`, runs them as supervised asyncio tasks, auto-restarts on crash, and applies pause / resume / restart commands received on `engine:control`.
- **`Watchdog`** — reads poller heartbeats from Redis and raises a silent-failure alarm when a poller stops producing.
- **`CircuitBreaker`** — trips open after repeated NSE failures (CLOSED → OPEN → HALF_OPEN) so a struggling data source backs off instead of hammering.
- **`ConsumerPool`** — a configurable number of workers that `BLPOP` a queue and run each item through its processor; pool size is a registry config value and resizable at runtime.
- **`NseSession`** — a persistent `httpx.AsyncClient` that manages NSE's required session cookies and refreshes them on 401/403.

## The corporate-announcements pipeline

This is the reference implementation every future alert type follows.

```
corp_ann poller                          corp_ann processor (ConsumerPool workers)
────────────────                         ─────────────────────────────────────────
NSE /corporate-announcements                BLPOP queue:corp_ann
      │ every ~5s                                 │
      ▼                                           ▼
for each item:                            SET dedup:corp_ann:{seq_id} NX (48h)  ── skip if duplicate
  SET inflight:{api}:{seq_id} NX (1h)           │
      │ (skip if already inflight)              ▼
      ▼                                   fetch attachment PDF (NseSession)
  RPUSH queue:corp_ann ─────────────────▶      │
                                                ▼
                                          render pages → images  (PyMuPDF, ProcessPoolExecutor)
                                                │
                                                ▼
                                          LLM: summarise + classify   (multimodal;
                                                │                       text fallback on failure)
                                                ▼
                                          persist Announcement (Postgres)
                                                │
                                                ▼
                                          cache result:{date}:{symbol}:{seq_id} (Redis, until midnight IST)
                                                │
                                                ▼
                                          PUBLISH alerts:{symbol}  →  delivery adapters
```

**Two-level deduplication.** A poller sets an `inflight:{api}:{item_id}` guard (1 h TTL) *before* enqueuing so the same item is never queued twice while in flight; a processor sets `dedup:{api}:{seq_id}` (48 h) *before* processing so an item is never analysed twice. On a processing failure the processor releases **both** keys (except on a rate-limit, where the consumer re-queues the item itself), so a transient outage — say the LLM provider was down — is reprocessed cleanly on the next run rather than being stranded until a TTL expires.

**Multimodal with fallback.** Pages are rendered to compact JPEGs and sent to a vision model in batches; the model can request more pages for long documents. If multimodal analysis fails, the processor falls back to extracting raw PDF text (truncated to a safe token budget) and analysing that. Every announcement is classified into one of: `acquisition`, `orders_or_contracts`, `new_product_launch`, `partnership_or_collaboration`, `financial_results`, `board_meeting`, `general_update`.

**Per-item timing.** The engine times every processed item and writes it to the event log — e.g. `processed INFY (Infosys Ltd) — financial_results in 24.09s` — giving operators live throughput visibility.

## The component registry

Pollers and processors are **not** wired in code — they are registered rows in Postgres (`poller_config`, `processor_config`, `processor_poller_link`). At startup the engine calls `load_enabled()`, which:

1. reads every **enabled** poller and processor row,
2. resolves each processor to its linked poller(s),
3. verifies the processor's declared **input schema** is compatible with the poller's **output schema**, and
4. skips — with a logged reason — any component that is broken, unlinked, or schema-incompatible, so one bad row never takes down the engine.

A component is just a Python module that satisfies a small contract:

| Kind | Module must expose | Example |
|---|---|---|
| Poller | `OutputSchema` (a Pydantic model) + `Poller` (a class) | `engine/pollers/corp_ann.py` |
| Processor | `InputSchema` (a Pydantic model) + `Processor` (a class) | `engine/processors/corp_ann.py` |

Register the built-in defaults (idempotent — it only enables *newly created* rows, so operator enable/disable choices survive restarts):

```bash
uv run python -m engine.register seed
```

Because registration is data, operators can enable, disable, reconfigure, and resize components entirely from the admin console — adding a brand-new alert type is a matter of shipping a contract-compliant module and registering it.

## The admin console

A dark, keyboard-friendly operations UI built on React + TanStack Query.

| Page | What it does |
|---|---|
| **Overview** | Split Pollers / Processors KPI cards and live health cards with inline controls. |
| **Pollers** | Every registered poller: state, error count, last poll, heartbeat, interval — pause / force-restart. |
| **Processors** | Every registered processor: state, queue depth, worker count — resize, pause, force-restart. |
| **Event log** | Rolling, human-readable engine events with datetime timestamps and per-item processing times. |
| **Alarms** | Active silent-failure and circuit-breaker alarms. |
| **Traders / Admins** | User management, scoped by role. |

<table>
  <tr>
    <td align="center"><img src="docs/img/pollers.png" alt="Pollers page" width="420"><br><em>Pollers</em></td>
    <td align="center"><img src="docs/img/processors.png" alt="Processors page" width="420"><br><em>Processors — resizable worker pools</em></td>
  </tr>
  <tr>
    <td colspan="2" align="center"><img src="docs/img/event_log.png" alt="Event log" width="840"><br><em>Event log — per-item processing times</em></td>
  </tr>
</table>

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Package manager | [UV](https://docs.astral.sh/uv/) |
| Gateway & API | FastAPI + Uvicorn |
| Auth | JWT (cookie-based) + bcrypt, role-based access control |
| Database | SQLAlchemy 2 (async) + Alembic + PostgreSQL |
| Cache / queue / pub-sub | Redis |
| PDF handling | PyMuPDF (render + text extraction) |
| LLM providers | OpenAI · Anthropic · Gemini (switchable; OpenAI-compatible endpoints supported) |
| Frontend | React + TypeScript + Vite + TanStack Query |
| Lint / format | Ruff (Python) · ESLint (TS) |
| Tests | pytest + fakeredis + aiosqlite · Vitest + Testing Library |
| Orchestration | Docker Compose |

## Getting started

### With Docker Compose (recommended)

Everything — Postgres, Redis, migrations, registry seeding, gateway, backend, engine, and the frontend — comes up with one command.

```bash
git clone https://github.com/vsaravind01/MarkAnn-Bot.git
cd MarkAnn
cp .env.example .env          # then fill in JWT_SECRET and your LLM key
docker compose up --build
```

Then open:

| URL | What |
|---|---|
| http://localhost:5173 | Admin console (create the first superuser on first run) |
| http://localhost:9150 | Gateway API |

The `migrate` and `register` services run once and exit; the engine waits for them before starting, so a fresh deployment comes up with the corporate-announcements feature already running.

### Locally with UV

Requires Postgres and Redis running, plus Python 3.13.

```bash
uv sync                                                            # install deps
alembic -c database/migrations/alembic.ini upgrade head           # migrate
uv run python -m engine.register seed                             # seed the registry

# in separate terminals:
uv run uvicorn gateway.main:app --port 9150 --reload              # gateway (public)
uv run uvicorn api.app:app --port 1530 --reload                  # backend (internal)
uv run python -m engine.main                                      # engine
cd app/admin && npm install && npm run dev                        # frontend
```

## Configuration

Copy `.env.example` to `.env` and fill it in. `.env` is gitignored — **never commit real secrets.**

```bash
# ── Auth (required) ──────────────────────────────────────────────
JWT_SECRET=            # generate: python -c "import secrets; print(secrets.token_hex(32))"

# ── LLM (required for the engine) ────────────────────────────────
LLM_PROVIDER=gemini    # gemini | openai | anthropic
GEMINI_API_KEY=
# GEMINI_MODEL=        # optional model override
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=

# ── OpenAI-compatible / local servers (optional) ─────────────────
# OPENAI_BASE_URL=http://host.docker.internal:8000/v1   # e.g. a local vLLM server
# OPENAI_MODEL=your-model-name

# ── Infrastructure (defaults suit docker compose) ────────────────
# DATABASE_URL=postgresql+asyncpg://markann:markann@postgres:5432/markann
# REDIS_URL=redis://redis:6379/0

# ── Engine tuning (optional) ─────────────────────────────────────
POLL_INTERVAL=5                  # seconds between NSE polls
# POLLER_SILENCE_THRESHOLD=600   # seconds before the watchdog raises a silence alarm
```

## API surface

All traffic goes through the **gateway** (`:9150`). Roles: `trader`, `admin`, `superuser`. `/admin/*` requires `admin`/`superuser`; `/api/v1/*` requires any authenticated user.

**Auth**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/register` | Self-register a trader |
| `POST` | `/auth/login` | Log in (sets auth cookies) |
| `POST` | `/auth/refresh` | Rotate the access token |
| `POST` | `/auth/logout` | Clear the session |
| `GET` | `/auth/me` | Current user |

**User management** (admin)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/admin/register` | Create an admin/superuser (bootstrap the first one) |
| `GET` | `/auth/admin/users` · `/users/{id}` | List / fetch users |
| `PATCH` | `/auth/admin/users/{id}` | Update a user |
| `GET` | `/auth/admin/traders` | List traders |
| `PATCH` | `/auth/admin/traders/{id}` | Update a trader |

**Engine operations** (admin — proxied to the backend)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/pollers` · `/admin/pollers/{api}` | Poller health |
| `POST` | `/admin/pollers/{api}/pause` · `/resume` · `/restart` | Control a poller |
| `GET` | `/admin/processors` · `/admin/processors/{api}` | Processor health |
| `PATCH` | `/admin/processors/{api}` | Resize a processor's worker pool |
| `POST` | `/admin/processors/{api}/pause` · `/resume` · `/restart` | Control a processor |
| `GET` | `/admin/processor-poller-links` | Registry wiring |
| `GET` | `/admin/events` | Engine event log |

**Watchlist** (any authenticated user)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/watchlist` | Subscribe to a symbol |
| `DELETE` | `/api/v1/watchlist` | Unsubscribe from a symbol |

## Testing

```bash
uv run pytest                       # backend — fakeredis + in-memory SQLite, no services needed
uv run pytest -m integration        # optional — hits real external APIs (needs .env.test)
cd app/admin && npm test            # frontend — Vitest + Testing Library
```

The default backend suite excludes `integration`-marked tests, so it runs offline with no Redis or Postgres required.

## Development

```bash
uv run ruff check .          # lint
uv run ruff format .         # format
cd app/admin && npm run lint # frontend lint
```

**Creating a migration**

```bash
alembic -c database/migrations/alembic.ini revision --autogenerate -m "description"
alembic -c database/migrations/alembic.ini upgrade head
```

**Conventions**

- [Google-style docstrings](https://google.github.io/styleguide/pyguide.html) for Python.
- Keep delivery adapters as separate consumers — don't embed them in the engine or API.
- Add a new alert type as a contract-compliant poller + processor pair, then register it — see [The component registry](#the-component-registry).

## Roadmap

- Ship the planned technical alert types (volume/price spikes, EMA crossover, S/R levels, Bollinger, VPoC).
- Additional delivery adapters (Telegram, email, SMS) as pub/sub consumers of `alerts:{symbol}`.
- Trader-facing watchlist and alert-feed UI.

## Documentation

Deeper documentation lives under [`docs/`](docs/). This README is the entry point; see the docs directory for architecture deep-dives, the component contract reference, and operational runbooks as they land.

## License

GNU General Public License v2.0 — see [LICENSE](LICENSE).
