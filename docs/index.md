# MarkAnn

**Real-time, AI-powered market-alert platform for Indian stock markets (NSE).**

MarkAnn watches NSE data streams, runs detection and AI analysis on what it finds, and delivers the results to users through configurable channels. It is built **API-first**: a gateway is the single public entrypoint, the backend API is the source of truth, an autonomous engine does the polling and processing, and a web console gives operators live control over the running system.

The first shipped feature is **AI-powered corporate announcements** — MarkAnn polls NSE press releases, reads the attached PDF (as images, with a text fallback), summarises and classifies it with an LLM, stores it, and publishes an alert to everyone watching that symbol.

![Operations dashboard](img/dashboard.png)

## Where to go next

<div class="grid cards" markdown>

- :material-sitemap: **[Architecture](architecture/overview.md)**

    How the four services fit together, and why. Start here to understand the system.

- :material-rocket-launch: **[Add an alert type](guides/add-an-alert-type.md)**

    The component contract, step by step — the main way MarkAnn is extended.

- :material-server-network: **[Operations](operations/deployment.md)**

    Deploy, drive the admin console, and follow the runbook when something breaks.

- :material-book-open-variant: **[Reference](reference/configuration.md)**

    Configuration, the data model, the Redis key map, and the API surface.

</div>

## What makes it different

- **Gateway-fronted, RBAC-secured.** A single public gateway handles authentication (cookie-based JWT), role checks, and rate limiting, then reverse-proxies to an internal backend the internet never touches.
- **DB-driven component registry.** Pollers and processors are *rows in Postgres*, not hardcoded wiring. The engine loads only what is enabled, validates schema compatibility, and skips anything broken — no redeploy required.
- **Live operational control.** Pause, resume, force-restart, and resize worker pools from the web console; commands travel over a Redis control channel to the engine in real time.
- **Self-healing engine.** A supervisor auto-restarts crashed tasks, a watchdog flags silent pollers, and a circuit breaker backs off failing data sources.
- **Provider-agnostic AI.** OpenAI, Anthropic, and Gemini are interchangeable via one env var — including OpenAI-compatible local servers such as vLLM.

## The stack at a glance

| Layer | Technology |
|---|---|
| Language | Python 3.13 (managed with [UV](https://docs.astral.sh/uv/)) |
| Gateway & API | FastAPI + Uvicorn |
| Database | SQLAlchemy 2 (async) + Alembic + PostgreSQL |
| Cache / queue / pub-sub | Redis |
| PDF handling | PyMuPDF |
| LLM | OpenAI · Anthropic · Gemini |
| Frontend | React + TypeScript + Vite + TanStack Query |
| Orchestration | Docker Compose |

!!! tip "New here?"
    The fastest path to a running system is the [Deployment guide](operations/deployment.md) — one `docker compose up` brings up Postgres, Redis, migrations, registry seeding, all three backend services, and the admin console.
