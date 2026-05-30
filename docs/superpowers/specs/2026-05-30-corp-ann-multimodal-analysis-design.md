# Corporate Announcements Multimodal Analysis Design

## Goal

Replace text-extraction-first announcement processing with a multimodal LLM pipeline that reads rendered PDF page images, returns both summary and category in one structured response, and adapts page batching to control token usage.

## Problem

The current processor extracts text directly from PDF files and passes that text to separate `summarize()` and `classify()` LLM calls. NSE announcement PDFs often contain poor embedded text, which makes extraction unreliable. The current approach also duplicates token usage by sending the same document content to the LLM twice and allows summary and category outputs to drift.

## Scope

This design covers the announcement processor and LLM provider interfaces required to support multimodal analysis of NSE corporate announcement PDFs.

Included:
- Render PDF pages to compressed images instead of relying on extracted text as the primary input.
- Replace separate summary and classification calls with one structured multimodal analysis call.
- Add iterative page batching with provisional-summary carryover.
- Add context-window retry behavior and a text-analysis fallback path.
- Preserve the existing persistence, Redis publishing, and event reporting flow.

Out of scope:
- Schema changes for storing confidence or intermediate summaries.
- Changes to alert delivery adapters or frontend presentation.
- Model-selection policy beyond enabling multimodal support in the existing providers.

## Current State

- [`engine/processor/corp_ann.py`](/Users/vsaravind/dev/MarkAnn/engine/processor/corp_ann.py) downloads the PDF, extracts text with [`engine/processor/pdf.py`](/Users/vsaravind/dev/MarkAnn/engine/processor/pdf.py), truncates oversized text, and calls `summarize(text)` and `classify(text, categories)`.
- [`llm/provider.py`](/Users/vsaravind/dev/MarkAnn/llm/provider.py) defines a text-only provider protocol.
- Provider implementations in [`llm/openai.py`](/Users/vsaravind/dev/MarkAnn/llm/openai.py), [`llm/anthropic.py`](/Users/vsaravind/dev/MarkAnn/llm/anthropic.py), and [`llm/gemini.py`](/Users/vsaravind/dev/MarkAnn/llm/gemini.py) only accept text.
- [`engine/processor/pdf.py`](/Users/vsaravind/dev/MarkAnn/engine/processor/pdf.py) currently exposes text extraction only.

## Proposed Architecture

### Processor Flow

1. Download the attachment PDF as today.
2. Render a batch of PDF pages to compressed JPEG images using PyMuPDF.
3. Call a new multimodal LLM provider method with:
   - page images
   - allowed categories
   - NSE metadata (`symbol`, `company`, `attchmntText`)
   - page-range metadata
   - optional provisional summary from the prior pass
4. Parse the structured LLM response containing summary, category, confidence, and optional `need_more_pages`.
5. If more pages are needed, render the next batch and call the same method again with the previous summary as provisional context.
6. Persist only the final summary and category once processing completes.
7. Publish the same Redis payload shape used today.

### LLM Contract

Replace the text-only provider contract with a single multimodal analysis method that returns a typed result.

Suggested interface shape:

```python
from dataclasses import dataclass

@dataclass(slots=True)
class AnnouncementAnalysis:
    summary: str
    category: str
    confidence: str
    need_more_pages: bool | None = None


@dataclass(slots=True)
class AnnouncementPageImage:
    page_number: int
    media_type: str
    image_bytes: bytes


class LLMProvider(Protocol):
    async def analyze_announcement(
        self,
        *,
        page_images: list[AnnouncementPageImage],
        categories: list[str],
        symbol: str,
        company: str,
        announcement_text: str,
        page_range_start: int,
        page_range_end: int,
        total_pages: int,
        provisional_summary: str | None = None,
    ) -> AnnouncementAnalysis: ...

    async def analyze_text_announcement(
        self,
        *,
        text: str,
        categories: list[str],
        symbol: str,
        company: str,
        announcement_text: str,
    ) -> AnnouncementAnalysis: ...
```

The text-analysis method exists only as a recovery path when multimodal analysis cannot complete.

### Iterative Batching Policy

#### Initial Pass

- Always start with pages `1..5`.
- This remains fixed even for long PDFs so the cheapest pass establishes whether the document is already obvious.

#### Subsequent Passes

- Default batch size remains `5` pages.
- If `total_pages > 15`, increase subsequent batch size to `10` pages.
- For each follow-up pass, send the previous summary as `provisional_summary` together with the next unseen page batch.

#### Provisional Summary Semantics

The prior summary is context, not a draft to patch.

The follow-up prompt must instruct the model to:
- treat `provisional_summary` as incomplete context from earlier pages
- read the new pages as primary evidence
- rewrite the full summary from scratch using both the provisional context and the current batch
- revise the category from scratch if new evidence changes the interpretation
- prefer the new pages whenever they extend or contradict the earlier summary

This avoids anchoring the model to merely correcting a previous draft while still preserving continuity across page batches.

### Prompt Style

The multimodal prompt should enforce a restrained analyst tone appropriate for alerts and UI payloads.

Summary style requirements:
- plain professional English
- concise and market-relevant
- no acknowledgements
- no conversational filler
- no ending quotes
- no emojis
- no bullet lists or tables
- no markdown
- no LLM phrasing such as “based on the document”
- no unnecessary hedging unless the announcement itself is ambiguous
- mention material business impact and any clearly visible material numbers when relevant

The prompt must also enforce strict structured output so providers can parse the response deterministically.

### `need_more_pages` Behavior

The prompt should request `need_more_pages` only when unseen pages remain.

Rules:
- If `total_pages <= page_range_end`, the model should not be asked to decide whether more pages are needed.
- If `total_pages > page_range_end`, the model should return whether more pages are needed after reviewing the current batch.
- The processor should still stop once all pages are exhausted, even if a model response is malformed.

### Image Rendering and Compression

Page rendering should optimize readability first and token usage second.

Requirements:
- render each page to JPEG
- cap render size so page text remains legible without sending oversized images
- apply moderate JPEG compression to reduce payload size
- tune JPEG quality into a moderate range, roughly `55-65`, unless testing shows readability loss

The processor should keep these values configurable as module-level constants so they can be tuned without changing business logic.

### Context-Window Retry Policy

If a provider rejects a multimodal request because of context-window or payload-size limits:
- reduce the current batch size to `floor(current_batch_size * 0.8)`
- retry the same pass with the smaller batch
- never reduce below `1` page
- preserve the same `provisional_summary` when retrying the pass

This policy applies per pass, which allows the processor to adapt dynamically to model limits without discarding earlier progress.

### Invalid Response Retry Policy

If the model returns malformed structured output or an invalid category:
- retry once with the same page batch and a stricter response-format instruction
- if the retry still fails, move to text fallback

This limits repeated retries while still giving the provider one repair attempt for transient formatting issues.

### Text Fallback Path

Multimodal image analysis becomes the primary path. Text extraction remains a recovery path.

Fallback conditions:
- repeated multimodal parse failure
- unrecoverable multimodal provider error
- multimodal request failure after batch-size reduction cannot proceed

Fallback behavior:
- extract text locally from the full PDF
- run one text-based analysis call returning the same structured result shape
- emit a warning event so fallback frequency is observable

The fallback should reuse the existing text extraction utility unless the file is later reorganized.

## Data Flow Details

### Final Persisted Data

Only these fields remain persisted and published from the LLM result:
- `summary`
- `category`

`confidence` and `need_more_pages` remain processing-time control fields and are not stored in the `Announcement` model in this iteration.

### Existing Payload Compatibility

The Redis and database payloads should remain unchanged except that their `summary` and `category` are now derived from the final multimodal analysis result.

This keeps downstream consumers stable while the processor internals evolve.

## File-Level Changes

### [`engine/processor/corp_ann.py`](/Users/vsaravind/dev/MarkAnn/engine/processor/corp_ann.py)

Responsibilities after the change:
- drive iterative batch processing
- decide initial and follow-up batch sizes
- hold retry logic for context-window shrinkage
- call the new multimodal provider method
- fall back to text analysis when required
- persist and publish the final result

### [`engine/processor/pdf.py`](/Users/vsaravind/dev/MarkAnn/engine/processor/pdf.py)

Responsibilities after the change:
- keep existing text extraction helper for fallback
- add a page-rendering helper that returns page count plus compressed JPEG payloads for requested page ranges

### [`llm/provider.py`](/Users/vsaravind/dev/MarkAnn/llm/provider.py)

Responsibilities after the change:
- define `AnnouncementAnalysis`
- define an image payload type for provider inputs
- replace text-only summarization/classification methods with multimodal analysis and text-fallback analysis methods

### Provider Implementations

- [`llm/openai.py`](/Users/vsaravind/dev/MarkAnn/llm/openai.py)
- [`llm/anthropic.py`](/Users/vsaravind/dev/MarkAnn/llm/anthropic.py)
- [`llm/gemini.py`](/Users/vsaravind/dev/MarkAnn/llm/gemini.py)

Responsibilities after the change:
- construct the multimodal prompt and payload for each vendor SDK
- parse the structured result into the shared `AnnouncementAnalysis` type
- support the text fallback analysis method using the same output schema and tone rules

## Testing Strategy

### Unit Tests

Update or add tests for:
- PDF page rendering helper returns expected page counts and image payloads
- processor first pass uses pages `1..5`
- processor uses `10`-page follow-up batches when `total_pages > 15`
- processor passes `provisional_summary` into later calls
- processor rewrites final stored data from the final analysis result
- processor shrinks batch size by `80%` on context-limit failures
- processor retries once on invalid structured output
- processor falls back to text analysis when multimodal analysis cannot recover
- provider methods parse structured responses into the shared result type

### Integration Coverage

Existing integration coverage can later be updated to exercise the multimodal Gemini path against a real announcement PDF. That update is part of implementation, not a separate design concern.

## Risks and Mitigations

### Risk: Summary quality degrades with aggressive image compression

Mitigation:
- cap dimensions conservatively
- keep JPEG quality moderate
- validate with representative NSE PDFs before tightening further

### Risk: Provisional summary anchors later passes incorrectly

Mitigation:
- instruct the model to rewrite the full summary from scratch on each later pass
- treat new pages as primary evidence

### Risk: Some providers may expose multimodal support differently

Mitigation:
- keep a single provider-level contract and let each implementation adapt to its SDK specifics
- preserve a text fallback path for resilience

### Risk: Long PDFs still consume multiple calls

Mitigation:
- keep the first pass cheap
- expand later batches only for longer documents
- shrink dynamically on context-window errors instead of failing outright

## Acceptance Criteria

The design is satisfied when:
- the processor no longer depends on extracted PDF text as the primary input path
- one LLM call produces both summary and category per batch
- the first pass always uses the first `5` pages
- subsequent batches use `5` pages by default and `10` pages when `total_pages > 15`
- later batches receive `provisional_summary` and rewrite the full summary from scratch
- `need_more_pages` is only requested when unseen pages remain
- batch size shrinks to `80%` on context-limit failures and retries the same pass
- a text fallback path exists for unrecoverable multimodal failures
- persisted and published output shape remains compatible with current consumers
