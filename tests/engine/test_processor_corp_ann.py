import json
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy import select

from database.models import Announcement
from database.redis import dedup_key, inflight_key, result_key
from engine.events import read_events
from engine.processors.base import ProcessorBase
from engine.processors.corp_ann import (
    ANNOUNCEMENT_CATEGORIES,
    CorporateAnnouncementsProcessor,
    InputSchema,
)
from engine.processors.pdf import RenderedPdfPages
from llm.provider import (
    AnnouncementAnalysis,
    LLMContextWindowError,
    LLMRateLimitError,
    LLMResponseFormatError,
)

SAMPLE_ITEM = {
    "seq_id": "106644730",
    "symbol": "INFY",
    "sm_name": "Infosys Limited",
    "attchmntText": "Infosys reports quarterly results.",
    "attchmntFile": "https://nsearchives.nseindia.com/test.pdf",
    "an_dt": "28-May-2026 10:00:00",
}


def test_input_schema_declares_required_fields():
    props = InputSchema.model_json_schema()["properties"]
    for field in ("seq_id", "symbol", "sm_name", "attchmntFile", "attchmntText", "an_dt"):
        assert field in props
        assert props[field]["type"] == "string"


def test_processor_subclasses_processor_base():
    assert issubclass(CorporateAnnouncementsProcessor, ProcessorBase)


def test_processor_default_config_has_pool_size():
    assert CorporateAnnouncementsProcessor.default_config() == {"pool_size": 8}


def _make_pdf_bytes(page_count: int) -> bytes:
    import fitz

    doc = fitz.open()
    for idx in range(page_count):
        page = doc.new_page()
        page.insert_text((50, 50), f"Page {idx + 1} announcement content")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


async def _corp_ann_warn_messages(redis) -> list[str]:
    events = await read_events(redis)
    return [
        str(event.get("msg", ""))
        for event in events
        if event.get("lvl") == "warn" and event.get("api") == "corp_ann"
    ]


async def test_skips_duplicate_item(fake_redis, async_db_session):
    await fake_redis.set(dedup_key("corp_ann", "106644730"), "1")
    mock_llm = AsyncMock()
    mock_session = MagicMock()
    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)
    mock_llm.analyze_announcement.assert_not_called()
    mock_llm.analyze_text_announcement.assert_not_called()
    mock_session.get.assert_not_called()
    pool.shutdown(wait=False)


async def test_releases_dedup_key_when_processing_fails(fake_redis, async_db_session):
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        side_effect=httpx.ConnectError("nse unreachable", request=pdf_request)
    )

    mock_llm = AsyncMock()
    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    with pytest.raises(httpx.ConnectError):
        await processor.process(SAMPLE_ITEM)

    assert await fake_redis.exists(dedup_key("corp_ann", "106644730")) == 0
    pool.shutdown(wait=False)


async def test_releases_dedup_key_when_db_commit_fails(fake_redis, async_db_session):
    pdf_bytes = _make_pdf_bytes(page_count=1)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.return_value = AnnouncementAnalysis(
        summary="Summary before commit error.",
        category="general_update",
        confidence="high",
        need_more_pages=False,
    )
    async_db_session.commit = AsyncMock(side_effect=RuntimeError("db commit failed"))

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    with pytest.raises(RuntimeError, match="db commit failed"):
        await processor.process(SAMPLE_ITEM)

    assert await fake_redis.exists(dedup_key("corp_ann", SAMPLE_ITEM["seq_id"])) == 0
    pool.shutdown(wait=False)


async def test_skips_non_pdf_attachment(fake_redis, async_db_session):
    attachment_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.html")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=b"<html>not a pdf</html>",
            headers={"content-type": "text/html"},
            request=attachment_request,
        )
    )

    mock_llm = AsyncMock()
    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    await processor.process(SAMPLE_ITEM)

    mock_llm.analyze_announcement.assert_not_called()
    mock_llm.analyze_text_announcement.assert_not_called()
    result = await async_db_session.execute(
        select(Announcement).where(Announcement.seq_id == SAMPLE_ITEM["seq_id"])
    )
    assert result.scalar_one_or_none() is None
    assert await fake_redis.exists(dedup_key("corp_ann", SAMPLE_ITEM["seq_id"])) == 0
    assert await fake_redis.get(result_key("INFY", SAMPLE_ITEM["seq_id"])) is None
    warn_messages = await _corp_ann_warn_messages(fake_redis)
    assert any("attachment not a PDF" in msg for msg in warn_messages)

    pool.shutdown(wait=False)


async def test_happy_path_multimodal_stores_and_publishes(fake_redis, async_db_session):
    pdf_bytes = _make_pdf_bytes(page_count=3)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.return_value = AnnouncementAnalysis(
        summary="Strong Q4 growth.",
        category="financial_results",
        confidence="high",
        need_more_pages=False,
    )

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)

    # dedup marked
    assert await fake_redis.exists(dedup_key("corp_ann", "106644730")) == 1

    # result cached in Redis
    cached = await fake_redis.get(result_key("INFY", "106644730"))
    assert cached is not None
    payload = json.loads(cached)
    assert payload["summary"] == "Strong Q4 growth."
    assert payload["category"] == "financial_results"

    # persisted to DB
    result = await async_db_session.execute(
        select(Announcement).where(Announcement.seq_id == "106644730")
    )
    ann = result.scalar_one_or_none()
    assert ann is not None
    assert ann.symbol == "INFY"
    assert ann.summary == "Strong Q4 growth."
    assert ann.category == "financial_results"
    assert ann.processing_mode == "multimodal"
    mock_llm.analyze_text_announcement.assert_not_called()

    pool.shutdown(wait=False)


async def test_malformed_announcement_datetime_uses_default_timestamp(fake_redis, async_db_session):
    pdf_bytes = _make_pdf_bytes(page_count=2)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    item = {**SAMPLE_ITEM, "an_dt": "not-a-real-date"}
    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.return_value = AnnouncementAnalysis(
        summary="Datetime fallback summary.",
        category="general_update",
        confidence="high",
        need_more_pages=False,
    )

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(item)

    result = await async_db_session.execute(
        select(Announcement).where(Announcement.seq_id == SAMPLE_ITEM["seq_id"])
    )
    ann = result.scalar_one_or_none()
    assert ann is not None
    assert ann.announced_at == datetime(2000, 1, 1, 0, 0, 0)

    pool.shutdown(wait=False)


async def test_provisional_summary_is_passed_to_later_batch(fake_redis, async_db_session):
    pdf_bytes = _make_pdf_bytes(page_count=8)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = [
        AnnouncementAnalysis(
            summary="First pass summary.",
            category="general_update",
            confidence="medium",
            need_more_pages=True,
        ),
        AnnouncementAnalysis(
            summary="Final summary from second pass.",
            category="orders_or_contracts",
            confidence="high",
            need_more_pages=False,
        ),
    ]

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)

    assert mock_llm.analyze_announcement.await_count == 2
    first_call_kwargs = mock_llm.analyze_announcement.await_args_list[0].kwargs
    second_call_kwargs = mock_llm.analyze_announcement.await_args_list[1].kwargs
    assert first_call_kwargs["page_range_start"] == 1
    assert first_call_kwargs["page_range_end"] == 5
    assert second_call_kwargs["page_range_start"] == 6
    assert second_call_kwargs["page_range_end"] == 8
    assert second_call_kwargs["provisional_summary"] == "First pass summary."

    cached = await fake_redis.get(result_key("INFY", "106644730"))
    assert cached is not None
    payload = json.loads(cached)
    assert payload["summary"] == "Final summary from second pass."
    assert payload["category"] == "orders_or_contracts"

    pool.shutdown(wait=False)


async def test_followup_batch_size_is_ten_when_total_pages_exceeds_fifteen(
    fake_redis, async_db_session
):
    pdf_bytes = _make_pdf_bytes(page_count=20)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = [
        AnnouncementAnalysis(
            summary="Pass one summary.",
            category="general_update",
            confidence="medium",
            need_more_pages=True,
        ),
        AnnouncementAnalysis(
            summary="Pass two summary.",
            category="general_update",
            confidence="medium",
            need_more_pages=False,
        ),
    ]

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)

    assert mock_llm.analyze_announcement.await_count == 2
    first_call_kwargs = mock_llm.analyze_announcement.await_args_list[0].kwargs
    second_call_kwargs = mock_llm.analyze_announcement.await_args_list[1].kwargs
    assert first_call_kwargs["page_range_start"] == 1
    assert first_call_kwargs["page_range_end"] == 5
    assert second_call_kwargs["page_range_start"] == 6
    assert second_call_kwargs["page_range_end"] == 15

    pool.shutdown(wait=False)


async def test_followup_batch_size_defaults_to_five_when_total_pages_at_most_fifteen(
    fake_redis, async_db_session
):
    pdf_bytes = _make_pdf_bytes(page_count=15)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = [
        AnnouncementAnalysis(
            summary="First pass summary.",
            category="general_update",
            confidence="medium",
            need_more_pages=True,
        ),
        AnnouncementAnalysis(
            summary="Second pass summary.",
            category="general_update",
            confidence="medium",
            need_more_pages=True,
        ),
        AnnouncementAnalysis(
            summary="Final summary.",
            category="general_update",
            confidence="high",
            need_more_pages=False,
        ),
    ]

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)

    assert mock_llm.analyze_announcement.await_count == 3
    first_call_kwargs = mock_llm.analyze_announcement.await_args_list[0].kwargs
    second_call_kwargs = mock_llm.analyze_announcement.await_args_list[1].kwargs
    third_call_kwargs = mock_llm.analyze_announcement.await_args_list[2].kwargs

    assert first_call_kwargs["page_range_start"] == 1
    assert first_call_kwargs["page_range_end"] == 5
    assert second_call_kwargs["page_range_start"] == 6
    assert second_call_kwargs["page_range_end"] == 10
    assert third_call_kwargs["page_range_start"] == 11
    assert third_call_kwargs["page_range_end"] == 15
    assert third_call_kwargs["provisional_summary"] == "Second pass summary."

    pool.shutdown(wait=False)


async def test_context_window_error_shrinks_batch_and_retries_same_pass(
    fake_redis, async_db_session
):
    pdf_bytes = _make_pdf_bytes(page_count=9)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = [
        LLMContextWindowError("context window exceeded"),
        AnnouncementAnalysis(
            summary="Recovered after shrink.",
            category="general_update",
            confidence="high",
            need_more_pages=False,
        ),
    ]

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)

    assert mock_llm.analyze_announcement.await_count == 2
    first_call_kwargs = mock_llm.analyze_announcement.await_args_list[0].kwargs
    second_call_kwargs = mock_llm.analyze_announcement.await_args_list[1].kwargs
    assert first_call_kwargs["page_range_start"] == 1
    assert first_call_kwargs["page_range_end"] == 5
    assert second_call_kwargs["page_range_start"] == 1
    assert second_call_kwargs["page_range_end"] == 4

    pool.shutdown(wait=False)


async def test_context_shrinks_to_min_and_then_falls_back_to_text(fake_redis, async_db_session):
    pdf_bytes = _make_pdf_bytes(page_count=7)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = [
        LLMContextWindowError("context exceeded at batch 5"),
        LLMContextWindowError("context exceeded at batch 4"),
        LLMContextWindowError("context exceeded at batch 3"),
        LLMContextWindowError("context exceeded at batch 2"),
        LLMContextWindowError("context exceeded at batch 1"),
    ]
    mock_llm.analyze_text_announcement.return_value = AnnouncementAnalysis(
        summary="Recovered via text fallback.",
        category="general_update",
        confidence="medium",
        need_more_pages=None,
    )

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)

    assert mock_llm.analyze_announcement.await_count == 5
    assert [
        call.kwargs["page_range_end"] for call in mock_llm.analyze_announcement.await_args_list
    ] == [5, 4, 3, 2, 1]
    mock_llm.analyze_text_announcement.assert_awaited_once()

    cached = await fake_redis.get(result_key("INFY", "106644730"))
    assert cached is not None
    payload = json.loads(cached)
    assert payload["summary"] == "Recovered via text fallback."
    assert payload["category"] == "general_update"
    warn_messages = await _corp_ann_warn_messages(fake_redis)
    assert any(
        message == "seq_id=106644730 (INFY): multimodal analysis failed, using text fallback"
        for message in warn_messages
    )

    pool.shutdown(wait=False)


async def test_empty_rendered_batch_falls_back_to_text_analysis(
    fake_redis, async_db_session, monkeypatch
):
    pdf_bytes = _make_pdf_bytes(page_count=2)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    def _render_no_pages(*args, **kwargs):
        del args, kwargs
        return RenderedPdfPages(total_pages=2, pages=[])

    monkeypatch.setattr("engine.processors.corp_ann.render_pdf_pages", _render_no_pages)

    mock_llm = AsyncMock()
    mock_llm.analyze_text_announcement.return_value = AnnouncementAnalysis(
        summary="Fallback after empty render batch.",
        category="general_update",
        confidence="medium",
        need_more_pages=None,
    )

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    processor._process_pool = None
    await processor.process(SAMPLE_ITEM)

    mock_llm.analyze_announcement.assert_not_awaited()
    mock_llm.analyze_text_announcement.assert_awaited_once()

    cached = await fake_redis.get(result_key("INFY", SAMPLE_ITEM["seq_id"]))
    assert cached is not None
    payload = json.loads(cached)
    assert payload["summary"] == "Fallback after empty render batch."
    assert payload["category"] == "general_update"
    warn_messages = await _corp_ann_warn_messages(fake_redis)
    assert any(
        message == "seq_id=106644730 (INFY): multimodal analysis failed, using text fallback"
        for message in warn_messages
    )

    pool.shutdown(wait=False)


async def test_falls_back_to_text_analysis_on_repeated_multimodal_format_failures(
    fake_redis, async_db_session
):
    pdf_bytes = _make_pdf_bytes(page_count=2)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = [
        LLMResponseFormatError("bad JSON"),
        LLMResponseFormatError("bad JSON retry"),
    ]
    mock_llm.analyze_text_announcement.return_value = AnnouncementAnalysis(
        summary="Fallback text summary.",
        category="general_update",
        confidence="medium",
        need_more_pages=None,
    )

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)

    assert mock_llm.analyze_announcement.await_count == 2
    first_call_kwargs = mock_llm.analyze_announcement.await_args_list[0].kwargs
    second_call_kwargs = mock_llm.analyze_announcement.await_args_list[1].kwargs
    assert first_call_kwargs["response_format_retry"] is False
    assert second_call_kwargs["response_format_retry"] is True
    mock_llm.analyze_text_announcement.assert_awaited_once()

    cached = await fake_redis.get(result_key("INFY", "106644730"))
    assert cached is not None
    payload = json.loads(cached)
    assert payload["summary"] == "Fallback text summary."
    assert payload["category"] == "general_update"
    result = await async_db_session.execute(
        select(Announcement).where(Announcement.seq_id == SAMPLE_ITEM["seq_id"])
    )
    ann = result.scalar_one()
    assert ann.processing_mode == "text"
    warn_messages = await _corp_ann_warn_messages(fake_redis)
    assert any(
        message == "seq_id=106644730 (INFY): multimodal analysis failed, using text fallback"
        for message in warn_messages
    )

    pool.shutdown(wait=False)


async def test_text_fallback_truncates_and_retries_response_format(
    fake_redis, async_db_session, monkeypatch
):
    pdf_bytes = _make_pdf_bytes(page_count=2)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )
    monkeypatch.setattr("engine.processors.corp_ann._MAX_TEXT_CHARS", 10)

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = LLMContextWindowError("force text fallback")
    mock_llm.analyze_text_announcement.side_effect = [
        LLMResponseFormatError("bad text JSON"),
        AnnouncementAnalysis(
            summary="Retried text fallback summary.",
            category="general_update",
            confidence="medium",
            need_more_pages=None,
        ),
    ]

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)

    assert mock_llm.analyze_text_announcement.await_count == 2
    first_call_kwargs = mock_llm.analyze_text_announcement.await_args_list[0].kwargs
    second_call_kwargs = mock_llm.analyze_text_announcement.await_args_list[1].kwargs
    assert first_call_kwargs["response_format_retry"] is False
    assert second_call_kwargs["response_format_retry"] is True
    assert len(first_call_kwargs["text"]) == 10
    assert first_call_kwargs["text"] == second_call_kwargs["text"]

    cached = await fake_redis.get(result_key("INFY", SAMPLE_ITEM["seq_id"]))
    assert cached is not None
    payload = json.loads(cached)
    assert payload["summary"] == "Retried text fallback summary."
    assert payload["category"] == "general_update"

    pool.shutdown(wait=False)


async def test_retry_after_post_commit_cache_failure_is_idempotent(fake_redis, async_db_session):
    pdf_bytes = _make_pdf_bytes(page_count=2)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.return_value = AnnouncementAnalysis(
        summary="Summary survives retry.",
        category="general_update",
        confidence="high",
        need_more_pages=False,
    )

    original_set = fake_redis.set
    original_publish = fake_redis.publish
    cache_key = result_key("INFY", "106644730")
    cache_failures = 0

    async def flaky_set(key, value, *args, **kwargs):
        nonlocal cache_failures
        if key == cache_key and cache_failures == 0:
            cache_failures += 1
            raise RuntimeError("cache write failed")
        return await original_set(key, value, *args, **kwargs)

    async def tracked_publish(channel, message, *args, **kwargs):
        return await original_publish(channel, message, *args, **kwargs)

    fake_redis.set = AsyncMock(side_effect=flaky_set)
    fake_redis.publish = AsyncMock(side_effect=tracked_publish)

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    with pytest.raises(RuntimeError, match="cache write failed"):
        await processor.process(SAMPLE_ITEM)

    assert await fake_redis.exists(dedup_key("corp_ann", "106644730")) == 0
    assert fake_redis.publish.await_count == 0

    await processor.process(SAMPLE_ITEM)

    assert fake_redis.publish.await_count == 1
    assert mock_llm.analyze_announcement.await_count == 2

    result = await async_db_session.execute(
        select(Announcement).where(Announcement.seq_id == "106644730")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].summary == "Summary survives retry."

    cached = await fake_redis.get(cache_key)
    assert cached is not None
    payload = json.loads(cached)
    assert payload["summary"] == "Summary survives retry."
    assert payload["category"] == "general_update"

    pool.shutdown(wait=False)


async def test_non_llm_multimodal_exception_propagates_without_text_fallback(
    fake_redis, async_db_session
):
    pdf_bytes = _make_pdf_bytes(page_count=2)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = RuntimeError("unexpected multimodal failure")

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    with pytest.raises(RuntimeError, match="unexpected multimodal failure"):
        await processor.process(SAMPLE_ITEM)

    mock_llm.analyze_text_announcement.assert_not_awaited()
    assert await fake_redis.exists(dedup_key("corp_ann", "106644730")) == 0
    pool.shutdown(wait=False)


async def test_announcement_categories_list():
    assert "financial_results" in ANNOUNCEMENT_CATEGORIES
    assert "acquisition" in ANNOUNCEMENT_CATEGORIES
    assert len(ANNOUNCEMENT_CATEGORIES) == 7


async def test_rate_limit_error_does_not_trigger_text_fallback(fake_redis, async_db_session):
    """LLMRateLimitError from multimodal must NOT fall back to text — both paths share the same API."""
    pdf_bytes = _make_pdf_bytes(page_count=2)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = LLMRateLimitError(
        "Rate limited.", retry_after=120.0
    )

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    with pytest.raises(LLMRateLimitError):
        await processor.process(SAMPLE_ITEM)

    mock_llm.analyze_text_announcement.assert_not_awaited()
    assert await fake_redis.exists(dedup_key("corp_ann", SAMPLE_ITEM["seq_id"])) == 0
    pool.shutdown(wait=False)


async def test_rate_limit_error_releases_dedup_key_and_propagates(fake_redis, async_db_session):
    """LLMRateLimitError must propagate out of process() and release the dedup key for retry."""
    pdf_bytes = _make_pdf_bytes(page_count=1)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = LLMRateLimitError("Rate limited.")

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    with pytest.raises(LLMRateLimitError):
        await processor.process(SAMPLE_ITEM)

    assert await fake_redis.exists(dedup_key("corp_ann", SAMPLE_ITEM["seq_id"])) == 0
    pool.shutdown(wait=False)


async def test_processing_failure_releases_inflight_for_reprocessing(fake_redis, async_db_session):
    """A non-rate-limit failure must release BOTH dedup and inflight keys so the poller
    re-enqueues the item on its next cycle (e.g. after an LLM provider outage)."""
    pdf_bytes = _make_pdf_bytes(page_count=1)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = RuntimeError("connection refused")
    mock_llm.analyze_text_announcement.side_effect = RuntimeError("connection refused")

    # Simulate the poller having marked the item in-flight before it was queued.
    await fake_redis.set(inflight_key("corp_ann", SAMPLE_ITEM["seq_id"]), "1", ex=3600)

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    with pytest.raises(RuntimeError):
        await processor.process(SAMPLE_ITEM)

    assert await fake_redis.exists(dedup_key("corp_ann", SAMPLE_ITEM["seq_id"])) == 0
    assert await fake_redis.exists(inflight_key("corp_ann", SAMPLE_ITEM["seq_id"])) == 0
    pool.shutdown(wait=False)


async def test_rate_limit_failure_keeps_inflight_for_consumer_requeue(fake_redis, async_db_session):
    """On a rate-limit error the consumer re-queues the item, so process() must NOT release
    the inflight key — doing so would let the poller enqueue a duplicate."""
    pdf_bytes = _make_pdf_bytes(page_count=1)
    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=pdf_request,
        )
    )

    mock_llm = AsyncMock()
    mock_llm.analyze_announcement.side_effect = LLMRateLimitError("Rate limited.")

    await fake_redis.set(inflight_key("corp_ann", SAMPLE_ITEM["seq_id"]), "1", ex=3600)

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )

    with pytest.raises(LLMRateLimitError):
        await processor.process(SAMPLE_ITEM)

    assert await fake_redis.exists(dedup_key("corp_ann", SAMPLE_ITEM["seq_id"])) == 0
    assert await fake_redis.exists(inflight_key("corp_ann", SAMPLE_ITEM["seq_id"])) == 1
    pool.shutdown(wait=False)
