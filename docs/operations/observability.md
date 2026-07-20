# Observability

MarkAnn's operational signals live in Redis and surface in the [admin console](admin-console.md). There's no external metrics stack yet — this page explains what the built-in signals mean and how to read them directly.

## The event log

The engine keeps a rolling, human-readable log in the Redis list `engine:events` (capped at 200 entries, newest first). It's exposed at `GET /admin/events` and rendered on the **Event log** page.

Each entry is `{ ts, lvl, msg, api? }`:

| Level | Badge | Meaning | Examples |
|---|---|---|---|
| `ok` | **OK** | Successful work | `processed INFY (Infosys Ltd) — financial_results in 24.09s` |
| `info` | **INFO** | Operator / lifecycle actions | `paused by operator`, `resumed by operator`, `restarted by operator` |
| `warn` | **WARN** | Recoverable issues & fallbacks | `fetch error #2 …`, `multimodal analysis failed, using text fallback`, `attachment not a PDF`, `watchdog restarted — heartbeat missing` |
| `crit` | **CRIT** | Serious faults | `circuit opened after 5 consecutive failures — …` |

Read it from the CLI:

```bash
docker compose exec redis redis-cli lrange engine:events 0 20
```

### Per-item processing time

Every successfully processed item logs its wall-clock duration (`engine.main._run_processor` times `process()` and appends `in <n>s`). This is the primary throughput signal — watch for durations creeping up, which usually means LLM latency or larger documents. **Skipped** items (duplicates, non-PDF) log nothing, so the log stays dense with real work.

## Poller health

The engine continuously writes health keys per poller; `GET /admin/pollers` aggregates them and the console renders them.

| Signal | Redis key | Healthy looks like |
|---|---|---|
| **Status** | `poller:{api}:status` | `running` |
| **Heartbeat** | `poller:{api}:heartbeat` | present (TTL = 3× interval) |
| **Last poll / success** | `poller:{api}:last_success` | recent epoch |
| **Errors** | `poller:{api}:error_count` | `0` |
| **Interval** | `poller:{api}:interval` | equal to `base_interval` (grows while backing off) |

A **missing heartbeat** means the poller stalled — the watchdog restarts it within a check cycle. A **rising error count** with a growing interval means `backing_off`. A `circuit_open` status means the breaker tripped. See the [runbook](runbook.md) for each.

```bash
docker compose exec redis redis-cli mget \
  poller:corp_ann:status \
  poller:corp_ann:heartbeat \
  poller:corp_ann:last_success \
  poller:corp_ann:error_count \
  poller:corp_ann:interval
```

## Processor health

| Signal | Source | Healthy looks like |
|---|---|---|
| **Status** | `processor:{api}:status` | `running` |
| **Queue depth** | `LLEN queue:{api}` | stable / draining, not monotonically climbing |
| **Workers** | pool size (registry config) | matches your intended concurrency |

**Queue depth** is the key backpressure signal: if it climbs without draining, processing is slower than ingestion — add workers (and restart) or, for local models, reduce concurrency. See [runbook: queue keeps growing](runbook.md#processor-queue-depth-keeps-growing).

```bash
docker compose exec redis redis-cli get  processor:corp_ann:status
docker compose exec redis redis-cli llen queue:corp_ann
```

## Alarms

The **Alarms** page surfaces active silent-failure and circuit-breaker conditions derived from the health keys and events above — a running-but-not-producing poller (silence past `POLLER_SILENCE_THRESHOLD`) or an open circuit. Treat a standing alarm as a prompt to open the event log and follow the matching [runbook](runbook.md) entry.

## Service logs

Container stdout complements the Redis signals — full tracebacks, LLM provider errors, and startup registry decisions (which components loaded or were skipped and why) land here:

```bash
docker compose logs -f engine        # pollers, processors, supervisor, watchdog
docker compose logs -f gateway       # auth, proxy, rate-limit
docker compose logs -f backend       # API requests
```

The engine logs at `INFO`, so you'll see each `Processed announcement …`, every registry skip reason, and every watchdog decision.
