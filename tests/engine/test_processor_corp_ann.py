import json
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import AsyncMock, MagicMock

import httpx
from sqlalchemy import select

from database.models import Announcement
from database.redis import dedup_key, result_key
from engine.processor.corp_ann import ANNOUNCEMENT_CATEGORIES, CorporateAnnouncementsProcessor

SAMPLE_ITEM = {
    "seq_id": "106644730",
    "symbol": "INFY",
    "sm_name": "Infosys Limited",
    "attchmntText": "Infosys reports quarterly results.",
    "attchmntFile": "https://nsearchives.nseindia.com/test.pdf",
    "an_dt": "28-May-2026 10:00:00",
}


async def test_skips_duplicate_item(fake_redis, async_db_session):
    await fake_redis.set(dedup_key("corp_ann", "106644730"), "1")
    mock_llm = AsyncMock()
    mock_session = MagicMock()
    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool, session=mock_session
    )
    await processor.process(SAMPLE_ITEM)
    mock_llm.summarize.assert_not_called()
    pool.shutdown(wait=False)


async def test_full_pipeline_stores_and_publishes(fake_redis, async_db_session):
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Q4 results strong growth")
    pdf_bytes = doc.tobytes()
    doc.close()

    pdf_request = httpx.Request("GET", "https://nsearchives.nseindia.com/test.pdf")
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=httpx.Response(200, content=pdf_bytes, request=pdf_request))

    mock_llm = AsyncMock()
    mock_llm.summarize.return_value = "Strong Q4 growth."
    mock_llm.classify.return_value = "financial_results"

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

    pool.shutdown(wait=False)


async def test_announcement_categories_list():
    assert "financial_results" in ANNOUNCEMENT_CATEGORIES
    assert "acquisition" in ANNOUNCEMENT_CATEGORIES
    assert len(ANNOUNCEMENT_CATEGORIES) == 7
