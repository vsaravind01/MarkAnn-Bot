# Core Alert Engine — Design Spec

**Date:** 2026-05-28
**Status:** Approved
**Scope:** Core alert engine, producer/consumer pipeline, LLM provider abstraction, results store, subscription system, poller health and supervision, fan-out to delivery adapters.

---

## 1. Goals

Build a low-latency, high-throughput alert engine for Indian stock market (NSE) data that:

- Polls scheduled NSE APIs at configurable intervals (default 5s) and feeds items into per-API in-memory queues
- Processes items through consumer pools (async + process pool for CPU work)
- Deduplicates items cheaply via Redis Sets on `seq_id`
- Summarises and classifies announcements via a pluggable LLM provider (OpenAI, Anthropic, or Gemini)
- Persists processed results in PostgreSQL (source of truth) and Redis (daily cache for low-latency reads)
- Publishes alerts to Redis pub/sub channels for delivery adapters to consume
- Supports tens of thousands of concurrent users watching multiple symbols
- Exposes admin API endpoints for dynamic pool resizing and poller control
- Keeps pollers alive reliably via a three-layer supervision model

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Engine Process                       │
│                                                          │
│  Pollers (async)                                         │
│  ├─ CorporateAnnouncementsPoller ──► Queue(corp_ann)     │
│  ├─ InsiderTradingPoller         ──► Queue(insider)      │
│  └─ MarketLargeDealsPoller       ──► Queue(large_deals)  │
│                          │                               │
│                   ConsumerPool (per queue)               │
│                   └─ Consumer coroutines (N, dynamic)    │
│                          │                               │
│                     Processor                            │
│                     ├─ Dedup (Redis SET, async)          │
│                     ├─ PDF fetch (async HTTP)            │
│                     ├─ PDF extract (ProcessPoolExecutor) │
│                     ├─ LLM summarise + classify (async)  │
│                     ├─ Persist (PostgreSQL + Redis)      │
│                     └─ Publish (Redis pub/sub)           │
│                                                          │
│  Supervisor + Watchdog (health, restart)                 │
└─────────────────────────────────────────────────────────┘
             │ Redis pub/sub: alerts:{symbol}
    ┌────────┴────────┐
    │                 │
┌───▼────┐      ┌─────▼──────┐      ┌─────────────┐
│Telegram│      │ WebSocket  │      │ Future: SMS  │
│Adapter │      │  Adapter   │      │  / Email     │
└────────┘      └────────────┘      └─────────────┘
```

**Runtime boundaries:**
- The engine is one process. Delivery adapters are separate services. They communicate exclusively through Redis (pub/sub + sets).
- The engine has no knowledge of users, delivery channels, or adapter implementations.
- PostgreSQL is the relational source of truth. Redis is the low-latency cache and message bus.

---

## 3. NSE API Classification

### Scheduled (polled by engine)

| API | Queue name | Default interval | Status |
|-----|-----------|-----------------|--------|
| `corporate-announcements` | `corp_ann` | 5s | Available in `nse_api_schema.yaml` |
| `insider-trading` | `insider` | 5s | Planned — NSE endpoint not yet documented |
| `market-large-deals` | `large_deals` | 5s | Planned — NSE endpoint not yet documented |

Planned APIs will be added to `nse_api_schema.yaml` and wired into the engine as they are discovered and validated. The engine is designed to add new pollers without structural changes.

These APIs produce data that requires heavy processing (PDF extraction, LLM calls) and must be queued to decouple fetching from processing.

### On-demand (called at processing time, no queue)

| API | When used |
|-----|-----------|
| `search_equities` | Symbol validation, user watchlist setup |
| `holidays` | Determining if market is open |
| Future price/volume feeds | Technical indicator alerts |

On-demand APIs are called directly via an async HTTP client at the point of need. They are not polled on a schedule.

---

## 4. Engine Internals

### 4.1 Pollers

Each scheduled API has a dedicated `Poller` instance running as an asyncio coroutine.

**Responsibilities:**
- Maintain an `httpx.AsyncClient` with persistent NSE session cookies
- Execute one API request per tick
- Put batched response items onto the API's `asyncio.Queue`
- Manage its own backoff state and circuit breaker
- Write health telemetry to Redis on every tick

**Tick lifecycle:**
```
tick:
  try:
    data = await fetch()          # httpx async request
    if data:
      await queue.put_nowait(data)
      update_health(success=True)
    reset_backoff()
    await sleep(interval)
  except SessionExpired:
    await refresh_nse_session()   # re-request NSE homepage for fresh cookies
    # retry immediately (no backoff — session errors are transient)
  except (NetworkError, HTTPError):
    update_health(success=False)
    await sleep(backoff.next())   # exponential backoff
```

**Backoff:** doubles on each failure, capped at `max_interval` (default 60s). Resets to `base_interval` on the next success.

**Circuit breaker** (within the poller):
- `closed` → normal operation
- After `failure_threshold` consecutive failures (default 5): → `open`
- In `open` state: sleep for `hold_off` (default 300s), then → `half_open`
- `half_open`: attempt one request. Success → `closed`. Failure → `open` again.
- Status written to `poller:{api}:status` in Redis.

**NSE session management:**
`httpx.AsyncClient` is instantiated once per poller with cookie persistence. NSE requires a valid session cookie obtained by requesting the NSE homepage. On a 401 or 403 response, the poller calls `refresh_session()` which issues a GET to the NSE homepage to obtain fresh cookies before retrying.

### 4.2 Consumer Pools

Each API queue has its own `ConsumerPool`. Pools are independent — corporate announcements can have more consumers than insider trading.

**Dynamic resizing:**
- The pool tracks live tasks in a `set[asyncio.Task]`
- `resize(n)` is called by the admin API at runtime without restart
- **Scale up**: spawn `(n - current)` new consumer coroutines
- **Scale down**: push `(current - n)` `STOP_SENTINEL` objects onto the queue. Consumers exit cleanly when they dequeue a sentinel, after finishing their current item. No forced cancellation.
- Configured size is persisted in PostgreSQL (`engine_config` table). On startup, the engine reads this table and uses the stored value; env vars (`CONSUMER_POOL_SIZE_*`) serve as the initial default only if no DB record exists yet (i.e., first run).

### 4.3 Processors

The processor for each API type encapsulates the full processing pipeline for one item.

**Corporate announcements pipeline:**

```
1. Dedup check
   → EXISTS dedup:corp_ann:{seq_id}  (Redis, async, O(1))
   → if present: skip item
   → if absent: continue

2. PDF fetch
   → async httpx GET of attchmntFile URL

3. PDF text extraction
   → loop.run_in_executor(process_pool, extract_pdf, pdf_bytes)
   → ProcessPoolExecutor (N workers = CPU core count)
   → truly parallel; event loop unblocked during extraction

4. LLM summarise + classify
   → await llm_provider.summarize(extracted_text)
   → await llm_provider.classify(extracted_text, ANNOUNCEMENT_CATEGORIES)
   → these are async I/O calls; multiple can be in-flight concurrently

5. Persist result
   → INSERT into PostgreSQL announcements table
   → SET result:{YYYYMMDD}:{symbol}:{seq_id} <json_payload> EX <seconds_until_midnight>
      (TTL is calculated at write time as seconds remaining until 23:59:59 local time)

6. Publish alert
   → PUBLISH alerts:{symbol} <json_payload>

7. Mark seen
   → SET dedup:corp_ann:{seq_id} 1 EX 172800  (48-hour TTL)
```

Steps 3 (PDF extraction in process pool) and 4 (LLM call over network) are both awaited sequentially per item — extraction must complete before summarisation can start. However, multiple items are processed concurrently across the consumer pool.

---

## 5. LLM Provider Abstraction

### Protocol

```python
class LLMProvider(Protocol):
    async def summarize(self, text: str) -> str: ...
    async def classify(self, text: str, categories: list[str]) -> str: ...
```

### Implementations

| Class | Provider | SDK |
|-------|----------|-----|
| `OpenAIProvider` | OpenAI | `openai` |
| `AnthropicProvider` | Anthropic | `anthropic` |
| `GeminiProvider` | Google Gemini | `google-generativeai` |

Active provider is selected at startup via `LLM_PROVIDER` env var (`openai` | `anthropic` | `gemini`). All processor code references only the `LLMProvider` protocol — no provider-specific imports outside the provider module.

### Announcement categories (for classification)

- `acquisition`
- `orders_or_contracts`
- `new_product_launch`
- `partnership_or_collaboration`
- `financial_results`
- `board_meeting`
- `general_update`

### Dependencies (replacing Cohere + Qdrant)

Remove: `cohere`, `qdrant-client`
Add: `openai>=1.0`, `anthropic>=0.30`, `google-generativeai>=0.8`

---

## 6. Results Store

### Two-layer architecture

| Layer | Technology | TTL | Role |
|-------|-----------|-----|------|
| Cache | Redis | Until 23:59:59 daily | Low-latency reads, high-throughput |
| Source of truth | PostgreSQL | Permanent | Authoritative record, fallback on cache miss |

### Redis key schema

```
result:{YYYYMMDD}:{symbol}:{seq_id}  →  JSON payload (see below)
  TTL: seconds_until_midnight at write time
```

### Result JSON payload

```json
{
  "seq_id": "106644730",
  "symbol": "INFY",
  "company": "Infosys Limited",
  "category": "financial_results",
  "announcement_text": "...",
  "summary": "...",
  "attachment_url": "https://nsearchives.nseindia.com/...",
  "announced_at": "2026-05-28T23:55:28+05:30",
  "processed_at": "2026-05-28T23:55:31+05:30"
}
```

### Cache read strategy

API layer reads:
1. `GET result:{today}:{symbol}:{seq_id}` from Redis
2. On miss → query PostgreSQL → optionally re-warm Redis with result + recalculated TTL

---

## 7. Deduplication

```
Redis key:  dedup:corp_ann:{seq_id}
Value:      "1"
TTL:        172800 seconds (48 hours)
Check:      EXISTS dedup:corp_ann:{seq_id}   → 1 means seen, 0 means new
Mark seen:  SET dedup:corp_ann:{seq_id} 1 EX 172800   (after successful processing)
```

The `seq_id` is the unique sequential identifier provided by NSE per announcement. It is reliable and monotonically increasing — no vector similarity or hashing needed. A 48-hour TTL is used to cover restarts and edge cases where the same announcement might reappear briefly after a market holiday.

---

## 8. Subscription and Fan-out

### Storage

**PostgreSQL (source of truth):**
```sql
users            (id, created_at, ...)
user_watchlist   (user_id, symbol, created_at, PRIMARY KEY (user_id, symbol))
user_channels    (user_id, channel_type TEXT, channel_config JSONB, created_at)
                  -- channel_type: "telegram" | "websocket" | future channels
```

**Redis (cache, kept in sync):**
```
watch:{symbol}           → SET of user_ids
user:{user_id}:channels  → SET of channel_type strings
```

On startup, the API server populates Redis Sets from PostgreSQL. On subscribe/unsubscribe, the request handler writes to PostgreSQL first, then updates Redis atomically (`SADD`/`SREM`).

### Fan-out flow

1. Engine: `PUBLISH alerts:{symbol} <json_payload>` — O(1), engine done
2. Delivery adapter: `PSUBSCRIBE alerts:*` — one wildcard subscription covers all symbols
3. On message for `alerts:INFY`:
   - `SMEMBERS watch:INFY` → set of watching user IDs
   - For each user ID: check `user:{id}:channels` — deliver only if this adapter's channel type is in the set
4. Deliver to matched users

Fan-out cost is paid by the adapter, not the engine. Multiple adapter services fan out in parallel and independently.

---

## 9. Poller Health and Supervision

Three independent failure modes require three distinct defences:

### Mode 1 — Task crash (exception kills the coroutine)

**Defence:** Supervisor pattern via `asyncio.Task.add_done_callback`.

Every poller task is registered with the `Supervisor`. The supervisor's `on_task_done` callback is attached to each task. If a task ends for any reason other than a clean `shutdown()` call, the supervisor schedules a restart after a short delay (default 2s). The poller never permanently dies from an unhandled exception.

### Mode 2 — Task stall (alive but blocked indefinitely)

**Defence:** Heartbeat with TTL in Redis + Watchdog coroutine.

Every poller writes on every tick (success or failure):
```
SET poller:{api}:heartbeat {unix_timestamp}  EX {3 * poll_interval}
```

TTL is `3 × poll_interval`. If three consecutive ticks are missed, the key expires.

The `Watchdog` coroutine runs every 30 seconds and calls `EXISTS poller:{api}:heartbeat` for each registered poller. If the key is absent, the watchdog instructs the supervisor to cancel and restart that task.

### Mode 3 — Silent data failure (alive, heartbeating, but no data produced)

**Defence:** `last_success` timestamp checked by Watchdog; triggers health alert, not auto-restart.

```
SET poller:{api}:last_success {unix_timestamp}  (no TTL, overwritten on each non-empty tick)
```

If `now - last_success > silence_threshold` (default 10 minutes), the Watchdog raises a structured health alert. This is not auto-restarted — silent failure may indicate a legitimate market halt, an NSE schema change, or a real bug. Human review is required.

### Redis health keys (per poller)

```
poller:{api}:heartbeat      → last tick timestamp  (TTL = 3 × interval)
poller:{api}:last_success   → last non-empty result timestamp
poller:{api}:status         → "running" | "backing_off" | "circuit_open" | "stopped"
poller:{api}:error_count    → consecutive failure count (reset on success)
poller:{api}:interval       → current effective poll interval
```

### Admin API controls (per poller)

- `GET  /admin/pollers`              → all pollers with live health from Redis
- `GET  /admin/pollers/{api}`        → single poller health
- `POST /admin/pollers/{api}/pause`  → graceful pause (completes current tick, stops scheduling)
- `POST /admin/pollers/{api}/resume` → resume from paused state
- `POST /admin/pollers/{api}/restart`→ cancel and restart immediately

---

## 10. Configuration and Environment Variables

```bash
# Engine
POLL_INTERVAL=5                     # base poll interval in seconds
CONSUMER_POOL_SIZE_CORP_ANN=8       # initial pool size (overridden by DB config at startup)
CONSUMER_POOL_SIZE_INSIDER=4
CONSUMER_POOL_SIZE_LARGE_DEALS=4
CIRCUIT_BREAKER_THRESHOLD=5         # consecutive failures before opening circuit
CIRCUIT_BREAKER_HOLDOFF=300         # seconds to hold off when circuit is open
POLLER_SILENCE_THRESHOLD=600        # seconds before silent failure alert

# LLM
LLM_PROVIDER=openai                 # openai | anthropic | gemini
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Infrastructure
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/markann

# Telegram delivery adapter
TELEGRAM_API_KEY=
```

---

## 11. Directory Structure

```
engine/
  poller.py          — Poller base class + per-API subclasses
  consumer.py        — ConsumerPool, consumer coroutine, STOP_SENTINEL
  processor/
    base.py          — Processor protocol
    corp_ann.py      — Corporate announcements processor
  supervisor.py      — Supervisor (task lifecycle) + Watchdog (staleness)
  circuit_breaker.py — CircuitBreaker state machine
  session.py         — NSE httpx.AsyncClient with cookie management
  health.py          — Redis health key read/write helpers

llm/
  provider.py        — LLMProvider Protocol
  openai.py          — OpenAIProvider
  anthropic.py       — AnthropicProvider
  gemini.py          — GeminiProvider
  factory.py         — get_provider() based on LLM_PROVIDER env var

database/
  models.py          — SQLAlchemy ORM models
  migrations/        — Alembic migrations
  redis.py           — Redis client + key helpers

api/
  app.py             — FastAPI app
  admin/
    pollers.py       — /admin/pollers routes
    pools.py         — /admin/pools routes
  v1/
    announcements.py — public alert endpoints
    watchlist.py     — subscribe/unsubscribe
```

---

## 12. Scaling Path

| Stage | Mechanism |
|-------|-----------|
| Initial (single machine) | asyncio engine + ProcessPoolExecutor |
| Horizontal scale-out | Replace `asyncio.Queue` with Redis Streams consumer groups; run N engine instances |
| Per-step scale-out | Only if a specific step (e.g., PDF extraction) is the measured bottleneck after horizontal scaling — extract to a dedicated worker pool service at that point |

No premature extraction of microservices. The engine is the horizontally-scalable unit.
