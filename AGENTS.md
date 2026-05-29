# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

**MarkAnn** is a market-alert platform for Indian stock markets (NSE). It monitors multiple data streams, generates alerts, and delivers them to users through configurable channels. The platform is built as an API-first system: a FastAPI backend is the single source of truth, the web dashboard is the primary user interface for configuring alerts, and delivery adapters (Telegram, etc.) are pluggable consumers of the alert engine.

**First feature**: AI-powered corporate announcements — fetches NSE press releases, summarizes them via LLM, and pushes to subscribed users.

**Planned alert types** (built incrementally after the first feature ships):
- Volume spike detection
- Price spike detection
- EMA crossover detection
- Resistance/Support level crossing detection
- Bollinger Band crossing detection
- Volume Point of Control (VPoC) spike detection

## Architecture

The platform has three layers:

```
[Data Sources]          NSE API (corporate announcements, price/volume feeds)
      ↓
[Alert Engine]          Fetches, processes, deduplicates, and emits alert events
      ↓
[Delivery Adapters]     Telegram bot  |  WebSocket (web dashboard)  |  future: email, SMS
```

**API** (`api/`) is the backbone — exposes REST endpoints for configuration and WebSocket streams for live alert delivery. The web dashboard and Telegram bot are both clients of this API.

**Alert engine** (`engine/`) is responsible for polling data sources, running detection logic, and publishing alert events.

**Delivery adapters** (`bot/`, and future adapters) are thin consumers that subscribe to alert events and forward them to users.

**Database**: SQLAlchemy + Alembic for users, subscriptions, and alert state. Qdrant for vector similarity (duplicate suppression on announcements). Alembic migrations run automatically on startup via the `@run_migration` decorator.

## Tooling

- **Python**: 3.13
- **Package manager**: [UV](https://docs.astral.sh/uv/) — use `uv sync` / `uv run`
- **Linter + formatter**: [Ruff](https://docs.astral.sh/ruff/)
- **Docstrings**: Google Style

```bash
uv sync                  # install all dependencies
uv run <script>          # run a script in the project venv
uv run ruff check .      # lint
uv run ruff format .     # format
```

## Environment Variables

```bash
# Telegram delivery adapter
TELEGRAM_API_KEY          # Telegram bot token

# AI / embeddings
COHERE_API_KEY            # Cohere (summarization + 1024-dim embeddings)

# Vector DB
QDRANT_URL                # Qdrant cloud URL
QDRANT_API_KEY            # Qdrant cloud API key

# Relational DB
DATABASE_URL              # SQLAlchemy connection string (default: SQLite)
```

## NSE API

See `nse_api_schema.yaml` for the full schema. Key endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/corporate-announcements?index=equities&from_date=…&to_date=…` | Fetch announcements; filter by `symbol` or `fo_sec` |
| `GET /api/smart-search/eqEtf?q=…` | Fuzzy equity search by company name |
| `GET /api/holiday-master?type=trading` | Trading holiday calendar |

NSE requires session cookies — plain `Origin`/`Referer` header spoofing is not enough. A session management layer (httpx `Client` with cookie persistence + periodic session refresh) is required.

## Database Migrations

Alembic lives in `database/migrations/`. To create a new migration:

```bash
alembic -c database/migrations/alembic.ini revision --autogenerate -m "description"
alembic -c database/migrations/alembic.ini upgrade head
```

Migrations run automatically on startup via the `@run_migration` decorator applied to the main entry point.
