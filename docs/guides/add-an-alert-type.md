# Add an alert type

Every alert type in MarkAnn is a **poller + processor pair** registered against the [component registry](../architecture/registry.md). Adding one requires no changes to the engine's startup, the API, or the console — you ship two contract-compliant modules and register them.

This guide builds a hypothetical `volume_spike` alert end to end.

## The shape of a component

A component is a Python module exposing a small, fixed set of names:

| Kind | Required names | Base class |
|---|---|---|
| Poller | `OutputSchema` (Pydantic model), `Poller` (class) | `engine.poller.Poller` |
| Processor | `InputSchema` (Pydantic model), `Processor` (class) | `engine.processors.base.ProcessorBase` |

The `OutputSchema` / `InputSchema` models are the **contract**: the registry validates that the fields a processor declares in `InputSchema` are present, with matching types, in the poller's `OutputSchema`. See the [contract reference](../reference/component-contract.md) for the exact rules.

## 1. Write the poller

`engine/pollers/volume_spike.py`

```python
from pydantic import BaseModel
from redis.asyncio import Redis

from engine.poller import Poller as BasePoller
from engine.session import NseSession


class OutputSchema(BaseModel):
    """Fields this poller guarantees to emit per item."""
    symbol: str
    volume: int
    avg_volume: int
    ts: str


class VolumeSpikePoller(BasePoller):
    def __init__(self, session: NseSession, redis: Redis, **kwargs) -> None:
        super().__init__(api_name="volume_spike", session=session, redis=redis, **kwargs)

    @classmethod
    def default_config(cls) -> dict:
        return {"base_interval": 30.0}

    def item_id(self, item: dict) -> str:
        # Stable per-item id → drives the inflight dedup guard.
        return f"{item['symbol']}:{item['ts']}"

    async def fetch(self) -> list[dict]:
        # Return a list of dicts matching OutputSchema. The base class handles
        # the poll loop, inflight guard, RPUSH, heartbeats, and backoff.
        ...


Poller = VolumeSpikePoller  # the registry looks for the name `Poller`
```

You only implement `fetch()` (and optionally `item_id()` and `default_config()`). The `BasePoller` provides the poll loop, the [inflight guard](../architecture/data-flow.md#deduplication-and-reprocessing), `RPUSH` onto `queue:volume_spike`, heartbeats, exponential backoff, and the [circuit breaker](../architecture/engine.md).

!!! tip "`item_id` matters"
    `item_id()` is what the inflight guard keys on. Return something **stable and unique per logical item** so re-fetching the same data doesn't re-enqueue it, but genuinely new data does. If NSE gives you a sequence id, use it (as `corp_ann` uses `seq_id`); otherwise compose one from the fields that identify the event.

## 2. Write the processor

`engine/processors/volume_spike.py`

```python
from pydantic import BaseModel

from engine.processors.base import ProcessorBase


class InputSchema(BaseModel):
    """Fields this processor needs from its poller."""
    symbol: str
    volume: int
    avg_volume: int
    ts: str


class VolumeSpikeProcessor(ProcessorBase):
    @classmethod
    def default_config(cls) -> dict:
        return {"pool_size": 4}

    def __init__(self, redis, db, llm, process_pool, session) -> None:
        self._redis = redis
        self._db = db
        # llm, process_pool, session are provided even if unused.

    async def process(self, item: dict) -> str | None:
        # Do the work. Return a short human summary when real work happened
        # (the engine logs it with the processing time), or None to skip.
        if item["volume"] < 3 * item["avg_volume"]:
            return None  # not a spike — skip, nothing logged
        # ... persist, cache, publish to alerts:{symbol} ...
        return f"{item['symbol']} volume {item['volume']:,} (3x avg)"


Processor = VolumeSpikeProcessor  # the registry looks for the name `Processor`
```

The engine constructs your processor with `redis`, `db` (a fresh async session per item), `llm`, `process_pool` (for CPU-bound work), and `session` (the `NseSession`). Return contract:

- **A summary string** → real work was done; the engine logs `processed <summary> in <n>s`.
- **`None`** → the item was skipped (not a spike, duplicate, unsupported); nothing is logged.
- **Raise** → a failure; the engine re-queues on `LLMRateLimitError`, otherwise logs it. Release your own dedup guards on the way out if you claimed any (see how `corp_ann` does it).

## 3. Register, link, and enable

```bash
# Register the poller (disabled by default)
uv run python -m engine.register poller engine.pollers.volume_spike

# Register the processor and link it to the poller (schema is validated here)
uv run python -m engine.register processor engine.processors.volume_spike \
    --poller volume_spike

# Turn them on
uv run python -m engine.register enable poller    volume_spike
uv run python -m engine.register enable processor volume_spike

# Confirm
uv run python -m engine.register list
```

If the processor's `InputSchema` asks for a field the poller's `OutputSchema` doesn't emit, the `processor` command **fails right here** with a clear message — you can't register an incompatible pair.

## 4. Restart the engine

The engine reads the registry at startup, so restart it to pick up the new components:

```bash
docker compose restart engine        # compose
# or restart your `python -m engine.main` process
```

The new poller and processor now appear on the **Pollers** and **Processors** pages of the [admin console](../operations/admin-console.md), fully controllable — pause, resume, force-restart, and (for the processor) resize — with **no frontend changes**, because the console renders whatever the registry reports.

## 5. Make the defaults ship (optional)

To have a fresh deployment come up with your component already running, add it to the seed lists in `engine/register.py`:

```python
_DEFAULT_POLLER_MODULES = ["engine.pollers.corp_ann", "engine.pollers.volume_spike"]
_DEFAULT_PROCESSOR_MODULES = [
    ("engine.processors.corp_ann", ["corp_ann"]),
    ("engine.processors.volume_spike", ["volume_spike"]),
]
```

`seed` runs as the one-shot `register` service in Compose and enables only newly-created rows, so this is safe on existing deployments.

## Checklist

- [ ] Poller module exposes `OutputSchema` and `Poller`, subclasses `BasePoller`, implements `fetch()`.
- [ ] Processor module exposes `InputSchema` and `Processor`, subclasses `ProcessorBase`, implements `process()` with the `str | None` return contract.
- [ ] `InputSchema` fields are a subset of `OutputSchema` fields (matching types).
- [ ] `item_id()` returns a stable, unique id.
- [ ] Registered, linked, enabled; `register list` looks right.
- [ ] Engine restarted; components visible and healthy in the console.
- [ ] Tests added under `tests/engine/`.
