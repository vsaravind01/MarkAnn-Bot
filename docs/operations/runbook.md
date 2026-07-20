# Runbook

Diagnostics and fixes for the situations you'll actually hit. Each entry lists the symptom, how to confirm it, and how to resolve it.

## No processor logs, only poller logs

**Symptom.** The engine shows pollers fetching, but no `processed …` events; the processor queue depth grows.

**Confirm.** Check for stranded `inflight` keys — items the poller enqueued but that failed processing and got stuck:

```bash
docker compose exec redis redis-cli --scan --pattern 'inflight:corp_ann:*' | head
docker compose exec redis redis-cli llen queue:corp_ann
```

**Cause.** This is the classic case behind the [reprocessing guard](../architecture/data-flow.md#deduplication-and-reprocessing). An earlier run consumed items and failed *after* the poller had set the `inflight` guard (e.g. the configured LLM provider was down). If the failure path doesn't release `inflight`, the guard lingers for its 1 h TTL and blocks re-enqueue — so a later, healthy deployment sees the poller running but nothing to process.

**Resolution.** Current code releases both `inflight` and `dedup` on non-rate-limit failures, so a recovered engine reprocesses on the next poll automatically. If you're on an older build or want to force it now:

```bash
# clear stranded guards so the poller re-enqueues on the next poll
docker compose exec redis redis-cli --scan --pattern 'inflight:corp_ann:*' \
  | xargs -r docker compose exec -T redis redis-cli del
```

Then confirm the provider is healthy (`LLM_PROVIDER` + key) and `docker compose restart engine`.

## Stalled processing after a provider outage

**Symptom.** You switched LLM providers (or restarted the engine) after a failed run, and old items still aren't processed.

**Confirm & resolve.** Same as above — this is the scenario the two-guard release was designed for. Verify the new provider works (see [LLM providers](../guides/llm-providers.md)), clear any lingering `inflight:*` keys, and restart the engine.

## A poller shows `circuit_open`

**Symptom.** A poller's state is `circuit_open` in the console; a `CRIT` event says "circuit opened after N consecutive failures".

**Cause.** The [circuit breaker](../architecture/engine.md) tripped after repeated NSE failures — commonly an expired/blocked NSE session, or NSE returning non-JSON.

**Resolution.** The breaker auto-recovers (OPEN → HALF_OPEN → CLOSED) once NSE responds again; the poller also refreshes its session on 401/403 automatically. If it stays open, check the event log for the underlying error, confirm outbound network to `nseindia.com`, then **Force-restart** the poller from the console.

## A poller is `backing_off`

**Symptom.** State `backing_off`, growing interval, incrementing error count.

**Cause.** Transient fetch failures; the poller doubles its interval up to `max_interval` (60 s) on each failure and resets on the next success. This is self-healing — usually no action needed. If it persists, treat it like `circuit_open` above.

## Watchdog restarted a poller / silent poller

**Symptom.** A `WARN` event: "watchdog restarted — heartbeat missing", or engine logs "has not produced data in Ns — manual review required".

**Cause.** The [watchdog](../architecture/engine.md#the-watchdog) found an expired heartbeat (poller stalled) and restarted it, **or** the poller is alive but hasn't produced data past `POLLER_SILENCE_THRESHOLD` (600 s). The latter is only logged, not auto-fixed.

**Resolution.** For a silence alarm, check whether NSE genuinely has no new data (often true outside market hours) versus a real fault (session blocked, wrong endpoint). Inspect the event log and NSE reachability.

## Processor queue depth keeps growing

**Symptom.** Queue depth on the Processors page climbs and doesn't drain.

**Cause.** Processing is slower than ingestion — often LLM latency (multimodal on many pages) or too few workers.

**Resolution.** Increase the worker pool: bump the count on the Processors page, then **Force-restart** the processor (resize applies on restart). If you're using a **local/small model**, the bottleneck is model throughput — reduce concurrency instead (see the [LLM memory note](../guides/llm-providers.md#openai-compatible-local-servers)).

## "Session expired" on login

**Symptom.** The login form shows "session expired" even in a fresh/incognito session.

**Cause.** Historically the frontend treated *every* `401` as an expired token and tried to refresh. A wrong password is also a `401`.

**Resolution.** Fixed — login requests skip the refresh path, so a bad credential now shows "Invalid credentials" (generic, [anti-enumeration](../architecture/security.md#error-semantics)) rather than "session expired". If you see this on an old build, update the frontend.

## Data "disappeared" after moving directories

**Symptom.** Users or announcements you created are gone after running Compose from a different path (e.g. a git worktree).

**Cause.** Compose namespaces volumes by directory basename, so a different directory uses **different** Postgres/Redis volumes. See the [volume note](deployment.md#per-directory-volume-names).

**Resolution.** Run from the original directory, or `docker volume ls` to find the right `*_postgres_data` volume.

## Quick reference

```bash
# engine logs
docker compose logs -f engine

# registry state
docker compose exec backend uv run python -m engine.register list

# queue + guards
docker compose exec redis redis-cli llen queue:corp_ann
docker compose exec redis redis-cli --scan --pattern 'inflight:*'
docker compose exec redis redis-cli --scan --pattern 'dedup:*'

# poller health keys
docker compose exec redis redis-cli mget \
  poller:corp_ann:status poller:corp_ann:heartbeat poller:corp_ann:error_count

# apply engine/poller/processor code changes
docker compose restart engine
```
