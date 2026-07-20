# LLM providers

The engine's LLM is provider-agnostic. One environment variable selects the backend; the rest of the pipeline — multimodal analysis, text fallback, rate-limit handling — is identical across providers.

## Selecting a provider

`llm/factory.py` reads `LLM_PROVIDER` and constructs the matching provider:

| `LLM_PROVIDER` | Class | Key |
|---|---|---|
| `gemini` | `GeminiProvider` | `GEMINI_API_KEY` |
| `openai` | `OpenAIProvider` | `OPENAI_API_KEY` |
| `anthropic` | `AnthropicProvider` | `ANTHROPIC_API_KEY` |

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
```

An unknown value raises at startup, so a typo fails fast rather than silently degrading.

## What a provider must do

All providers implement the same interface (`llm/provider.py`), so the [corp_ann processor](../architecture/data-flow.md#the-corporate-announcements-pipeline) doesn't care which is active:

- `analyze_announcement(...)` — **multimodal**: takes rendered page images + context and returns an `AnnouncementAnalysis` (summary, category, and whether more pages are needed).
- `analyze_text_announcement(...)` — **text fallback**: takes extracted PDF text and returns the same structure.

Both raise a shared exception hierarchy the pipeline handles uniformly:

| Exception | Meaning | Pipeline response |
|---|---|---|
| `LLMRateLimitError(retry_after)` | Provider 429 | Item re-queued; worker sleeps `retry_after`. |
| `LLMContextWindowError` | Prompt too large | Multimodal batch is shrunk and retried. |
| `LLMResponseFormatError` | Malformed structured output | One reformat retry. |
| `LLMProviderError` | Other provider failure | Multimodal → falls back to text analysis. |

## Model overrides

Each provider has a sensible default model; override it per provider:

```bash
# Gemini
GEMINI_MODEL=gemini-2.0-flash

# OpenAI
OPENAI_MODEL=gpt-4o-mini
```

## OpenAI-compatible & local servers

The OpenAI provider honours `OPENAI_BASE_URL`, so any OpenAI-compatible endpoint works — including a **local vLLM** server for offline experimentation with no API costs.

```bash
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://host.docker.internal:8000/v1   # local vLLM
OPENAI_MODEL=mlx-community/Qwen3-VL-4B-Instruct-4bit
OPENAI_API_KEY=not-needed                             # placeholder for local servers
```

!!! note "`host.docker.internal` from the engine container"
    The Compose `engine` service declares `extra_hosts: ["host.docker.internal:host-gateway"]`, so a container can reach a server running on the host (including on Linux). Point `OPENAI_BASE_URL` at `http://host.docker.internal:<port>/v1`, not `localhost` — inside the container `localhost` is the container itself.

!!! warning "Local multimodal models are memory-hungry"
    Multimodal analysis sends several page images per request, and the processor pool runs multiple items concurrently. A small quantised vision model on a laptop can exhaust memory under that load. When experimenting locally, **reduce the processor pool size** (resize `corp_ann` to `1` in the console, or set `pool_size` in its registry config) so only one item is analysed at a time.

## Rate-limit handling

Providers detect 429s per their own API shape and raise `LLMRateLimitError` with a `retry_after` when the provider supplies one. The [ConsumerPool](../architecture/engine.md#the-consumerpool) re-queues the item and backs off, and the processor keeps its `inflight` guard so the re-queue isn't deduplicated away. In-provider inline retries are also capped so a single item can't block a worker indefinitely.
