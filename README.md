<div align="center">
  <img src="assets/avatar.png" alt="MarkAnn" width="180" height="180" style="border-radius: 12px;">
  <h1>MarkAnn</h1>
  <p>Real-time market alert platform for Indian stock markets (NSE)</p>
</div>

---

MarkAnn is an **API-first** alert platform that monitors NSE data streams, runs detection and AI analysis, and delivers alerts to users through configurable channels. The FastAPI backend is the single source of truth; a web dashboard is the primary user interface; delivery adapters (Telegram, WebSocket, etc.) are pluggable consumers of the alert engine.

## Alert types

| Status | Alert |
|---|---|
| ✅ Live | AI-powered corporate announcements — fetches NSE press releases, extracts PDF text, summarises and classifies via LLM, pushes to subscribers |
| 🔜 Planned | Volume spike detection |
| 🔜 Planned | Price spike detection |
| 🔜 Planned | EMA crossover detection |
| 🔜 Planned | Resistance / Support level crossing |
| 🔜 Planned | Bollinger Band crossing |
| 🔜 Planned | Volume Point of Control (VPoC) spike |

## Architecture

```
[NSE API]
    │  polls every N seconds (default 5s)
    ▼
[Alert Engine]  ──  asyncio Queue per data stream
    │               ConsumerPool (configurable workers)
    │               ProcessPoolExecutor (PDF extraction)
    │               LLM provider (summarise + classify)
    │               PostgreSQL  (permanent store)
    │               Redis       (dedup · daily cache · pub/sub)
    ▼
[FastAPI]       ──  REST  (config, watchlist, admin)
    │               WebSocket  (live alert stream)
    ▼
[Delivery adapters]  ──  Telegram bot
                         WebSocket client (web dashboard)
                         …future: email, SMS
```

**Engine internals**

- `Supervisor` — monitors asyncio tasks and auto-restarts pollers on crash
- `Watchdog` — checks Redis heartbeats every 30 s; logs a silent-failure alert when a poller stops producing data
- `CircuitBreaker` — backs off after repeated NSE API failures (CLOSED → OPEN → HALF_OPEN)
- `NseSession` — persistent `httpx.AsyncClient` with NSE cookie management

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Package manager | [UV](https://docs.astral.sh/uv/) |
| API | FastAPI + Uvicorn |
| Database | SQLAlchemy 2 (async) + Alembic + PostgreSQL |
| Cache / pub-sub | Redis |
| PDF extraction | PyMuPDF |
| LLM providers | OpenAI · Anthropic · Gemini (switchable via env var) |
| Linter / formatter | Ruff |

## Prerequisites

- Python 3.13
- PostgreSQL
- Redis
- API key for one LLM provider (OpenAI, Anthropic, or Gemini)

## Setup

```bash
git clone https://github.com/vsaravind01/MarkAnn.git
cd MarkAnn
uv sync
```

Copy `.env.example` (or create `.env`) and fill in the required values:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/markann

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM — set LLM_PROVIDER to one of: openai | anthropic | gemini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=ant-...
# GEMINI_API_KEY=gem-...

# Engine tuning (optional)
POLL_INTERVAL=5                   # seconds between NSE polls
POLLER_SILENCE_THRESHOLD=600      # seconds before watchdog logs a silent-failure alert
CONSUMER_POOL_SIZE_CORP_ANN=8     # initial worker count (overridden by DB config at runtime)
```

## Running

**Database migrations** (run once, then on each schema change):

```bash
alembic -c database/migrations/alembic.ini upgrade head
```

**Alert engine:**

```bash
uv run python -m engine.main
```

**API server:**

```bash
uv run uvicorn api.app:app --reload
```

## API overview

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/pollers` | List all pollers and their health |
| `GET` | `/admin/pollers/{api}` | Single poller health |
| `POST` | `/admin/pollers/{api}/pause` | Pause a poller |
| `POST` | `/admin/pollers/{api}/resume` | Resume a paused poller |
| `POST` | `/admin/pollers/{api}/restart` | Force-restart a poller |
| `GET` | `/admin/pools/{api}` | Get consumer pool size |
| `PATCH` | `/admin/pools/{api}` | Resize consumer pool at runtime |
| `POST` | `/api/v1/watchlist` | Subscribe a user to a symbol |
| `DELETE` | `/api/v1/watchlist` | Unsubscribe a user from a symbol |

## Testing

```bash
uv run pytest tests/ -v
```

The test suite uses `fakeredis` and an in-memory SQLite database — no running Redis or PostgreSQL required.

## Creating a new migration

```bash
alembic -c database/migrations/alembic.ini revision --autogenerate -m "description"
alembic -c database/migrations/alembic.ini upgrade head
```

## Contributing

- Open an issue before starting work on a new feature or significant bug fix.
- Follow [Google Style Docstrings](https://google.github.io/styleguide/pyguide.html).
- Run `uv run ruff check . && uv run ruff format .` before committing.
- Keep delivery adapters as separate services — do not embed them in the engine or API.

## License

GNU General Public License v2.0 — see [LICENSE](LICENSE).
