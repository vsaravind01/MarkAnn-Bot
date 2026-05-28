import json
import respx
import httpx
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import AsyncMock
from engine.processor.corp_ann import CorporateAnnouncementsProcessor, ANNOUNCEMENT_CATEGORIES
from database.redis import dedup_key

SAMPLE_ITEM = {
    "seq_id": "106644730",
    "symbol": "INFY",
    "sm_name": "Infosys Limited",
    "attchmntText": "Infosys reports quarterly results.",
    "attchmntFile": "https://nsearchives.nseindia.com/test.pdf",
    "an_dt": "28-May-2026 10:00:00",
}


@respx.mock
async def test_skips_duplicate_item(fake_redis, async_db_session):
    await fake_redis.set(dedup_key("corp_ann", "106644730"), "1")
    mock_llm = AsyncMock()
    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool
    )
    await processor.process(SAMPLE_ITEM)
    mock_llm.summarize.assert_not_called()
    pool.shutdown(wait=False)


@respx.mock
async def test_full_pipeline_stores_and_publishes(fake_redis, async_db_session):
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Q4 results strong growth")
    pdf_bytes = doc.tobytes()
    doc.close()

    respx.get("https://nsearchives.nseindia.com/test.pdf").mock(
        return_value=httpx.Response(200, content=pdf_bytes)
    )

    mock_llm = AsyncMock()
    mock_llm.summarize.return_value = "Strong Q4 growth."
    mock_llm.classify.return_value = "financial_results"

    pool = ProcessPoolExecutor(max_workers=1)
    processor = CorporateAnnouncementsProcessor(
        redis=fake_redis, db=async_db_session, llm=mock_llm, process_pool=pool
    )
    await processor.process(SAMPLE_ITEM)

    # dedup marked
    assert await fake_redis.exists(dedup_key("corp_ann", "106644730")) == 1

    # result cached in Redis
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    cached = await fake_redis.get(f"result:{today}:INFY:106644730")
    assert cached is not None
    payload = json.loads(cached)
    assert payload["summary"] == "Strong Q4 growth."
    assert payload["category"] == "financial_results"

    pool.shutdown(wait=False)


async def test_announcement_categories_list():
    assert "financial_results" in ANNOUNCEMENT_CATEGORIES
    assert "acquisition" in ANNOUNCEMENT_CATEGORIES
    assert len(ANNOUNCEMENT_CATEGORIES) == 7
