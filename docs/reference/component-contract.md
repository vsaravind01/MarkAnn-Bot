# Component contract

The exact interface a poller or processor module must satisfy to be registered and loaded. For a worked walkthrough, see [Add an alert type](../guides/add-an-alert-type.md).

## Module-level names

The [registry loader](../architecture/registry.md) imports the module and looks up fixed names. A module missing any of them raises `ContractError` at registration and is skipped (with a log) at startup.

| Kind | Required name | Must be |
|---|---|---|
| Poller | `OutputSchema` | a Pydantic `BaseModel` — the fields each emitted item guarantees |
| Poller | `Poller` | the poller class |
| Processor | `InputSchema` | a Pydantic `BaseModel` — the fields the processor requires |
| Processor | `Processor` | the processor class |

The schemas are converted to JSON Schema with `.model_json_schema()` and stored in the registry; the classes' `default_config()` (if defined) seeds the stored config.

## `api_name`

Derived from the module path's last segment: `engine.pollers.corp_ann` → `corp_ann`. It is the component's identity in Redis keys, API paths, and the console, and must be unique across pollers and unique across processors.

## Poller class

Subclass `engine.poller.Poller` (an `ABC`).

```python
class Poller(ABC):
    def __init__(self, api_name, session, redis,
                 base_interval=5.0, max_interval=60.0,
                 failure_threshold=5, circuit_hold_off=300.0): ...

    @abstractmethod
    async def fetch(self) -> list[dict]: ...     # you implement this

    def item_id(self, item: dict) -> str: ...    # override for a stable id
```

| Member | Who implements | Contract |
|---|---|---|
| `fetch()` | **you (required)** | Return a list of dicts, each conforming to `OutputSchema`. Raise on failure — the base class records it against the circuit breaker and backs off. |
| `item_id(item)` | you (optional) | Stable, unique id per logical item; drives the `inflight` guard. Defaults to a hash of the item. |
| `default_config()` | you (optional, classmethod) | Default config dict, e.g. `{"base_interval": 5.0}`. |
| the run loop | base class | Heartbeats, `inflight` guard, `RPUSH` to `queue:{api}`, status writes, backoff, circuit breaker, NSE session refresh on 401/403. |

Expose the class as `Poller`:

```python
Poller = CorporateAnnouncementsPoller
```

## Processor class

Subclass `engine.processors.base.ProcessorBase`.

```python
class ProcessorBase(ABC):
    @classmethod
    def default_config(cls) -> dict:
        return {}

    @abstractmethod
    async def process(self, item: dict) -> str | None: ...
```

The engine constructs the processor **once per item** with these keyword arguments:

| Argument | What it is |
|---|---|
| `redis` | The shared async Redis client. |
| `db` | A **fresh** `AsyncSession` scoped to this item. |
| `llm` | The configured [LLM provider](../guides/llm-providers.md). |
| `process_pool` | A `ProcessPoolExecutor` for CPU-bound work (e.g. PDF rendering). |
| `session` | The shared `NseSession` for outbound HTTP. |

### The `process()` return contract

| Return | Meaning | Engine behaviour |
|---|---|---|
| `str` | Real work was done | Logs `processed <summary> in <n>s` to the event log. |
| `None` | Item skipped (duplicate, unsupported, no-op) | Nothing logged. |
| *raises* | Failure | `LLMRateLimitError` → item re-queued + backoff; any other exception → logged. |

!!! important "Release your own guards on failure"
    If your `process()` claims a `dedup:{api}:{seq_id}` (and relies on the poller's `inflight`) guard, release it in your error path so the item can be retried — **except** on `LLMRateLimitError`, where the consumer re-queues and the `inflight` guard must stay. Follow the pattern in `engine/processors/corp_ann.py`. Full rationale: [Data Flow — deduplication & reprocessing](../architecture/data-flow.md#deduplication-and-reprocessing).

Expose the class as `Processor`:

```python
Processor = CorporateAnnouncementsProcessor
```

## Schema compatibility rule

At registration and at startup, `schema_incompatibilities(input_schema, output_schema)` checks that **every field in the processor's `InputSchema`** is:

1. **present** in the poller's `OutputSchema`, and
2. of a **matching type**.

Extra fields in the poller output are fine (the processor simply ignores them). A missing or mistyped required field makes the pair incompatible — registration fails and the loader skips the processor. This is what guarantees a processor is only ever fed a poller that produces what it needs.

## `config`

Both kinds may define `default_config()`. Stored config is the module defaults merged under any operator overrides (e.g. a resized `pool_size`). The engine merges module defaults with the stored JSON at load time, so new default keys added in code appear automatically while operator overrides persist. Well-known keys:

| Key | Kind | Meaning |
|---|---|---|
| `base_interval` | poller | Seconds between polls. |
| `pool_size` | processor | Worker count for the `ConsumerPool`. |
