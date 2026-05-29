import asyncio
import json
import logging
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime

import pytz
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Announcement
from database.redis import (
    alert_channel,
    dedup_key,
    result_key,
    seconds_until_midnight,
)
from engine.events import push_event
from engine.processor.pdf import extract_pdf_text
from engine.session import NseSession
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# Gemini's limit is 262 144 tokens; ~4 chars/token gives ~1 M chars.
# We cap well below that to leave headroom for prompt overhead.
_MAX_TEXT_CHARS = 200_000

ANNOUNCEMENT_CATEGORIES = [
    "acquisition",
    "orders_or_contracts",
    "new_product_launch",
    "partnership_or_collaboration",
    "financial_results",
    "board_meeting",
    "general_update",
]

_IST = pytz.timezone("Asia/Kolkata")


def _parse_nse_datetime(dt_str: str) -> datetime:
    naive = datetime.strptime(dt_str, "%d-%b-%Y %H:%M:%S")
    return _IST.localize(naive).replace(tzinfo=None)


class CorporateAnnouncementsProcessor:
    def __init__(
        self,
        redis,
        db: AsyncSession,
        llm: LLMProvider,
        process_pool: ProcessPoolExecutor,
        session: NseSession,
    ) -> None:
        self._redis = redis
        self._db = db
        self._llm = llm
        self._process_pool = process_pool
        self._session = session

    async def process(self, item: dict) -> None:
        seq_id = item.get("seq_id", "")
        symbol = item.get("symbol", "")

        acquired = await self._redis.set(dedup_key("corp_ann", seq_id), "1", nx=True, ex=172800)
        if not acquired:
            logger.debug(f"Skipping duplicate seq_id={seq_id}")
            return

        attachment_url = item.get("attchmntFile")
        if not attachment_url:
            logger.warning(f"No attachment for seq_id={seq_id}, skipping")
            return

        response = await self._session.get(attachment_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/pdf" not in content_type:
            logger.warning(
                f"seq_id={seq_id} attachment is not a PDF "
                f"(content-type={content_type!r}) — skipping"
            )
            await push_event(
                self._redis, "warn",
                f"skipped seq_id={seq_id} ({symbol}): attachment not a PDF",
                api="corp_ann",
            )
            return
        pdf_bytes = response.content

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(self._process_pool, extract_pdf_text, pdf_bytes)

        if len(text) > _MAX_TEXT_CHARS:
            logger.warning(
                f"seq_id={seq_id} PDF text truncated "
                f"({len(text)} → {_MAX_TEXT_CHARS} chars) before LLM"
            )
            await push_event(
                self._redis, "warn",
                f"seq_id={seq_id} ({symbol}): PDF truncated {len(text):,} → {_MAX_TEXT_CHARS:,} chars",
                api="corp_ann",
            )
            text = text[:_MAX_TEXT_CHARS]

        summary = await self._llm.summarize(text)
        category = await self._llm.classify(text, ANNOUNCEMENT_CATEGORIES)

        announced_at = _parse_nse_datetime(item.get("an_dt", "01-Jan-2000 00:00:00"))
        company = item.get("sm_name", "")
        announcement_text = item.get("attchmntText", "")

        ann = Announcement(
            seq_id=seq_id,
            symbol=symbol,
            company=company,
            category=category,
            announcement_text=announcement_text,
            summary=summary,
            attachment_url=attachment_url,
            announced_at=announced_at,
        )
        self._db.add(ann)
        await self._db.commit()

        payload = {
            "seq_id": seq_id,
            "symbol": symbol,
            "company": company,
            "category": category,
            "announcement_text": announcement_text,
            "summary": summary,
            "attachment_url": attachment_url,
            "announced_at": announced_at.isoformat(),
            "processed_at": datetime.now(tz=UTC).isoformat(),
        }
        payload_json = json.dumps(payload)

        await self._redis.set(
            result_key(symbol, seq_id),
            payload_json,
            ex=seconds_until_midnight(),
        )
        await self._redis.publish(alert_channel(symbol), payload_json)

        logger.info(f"Processed announcement seq_id={seq_id} symbol={symbol} category={category}")
        await push_event(
            self._redis, "ok",
            f"processed {symbol} ({company}) — {category}",
            api="corp_ann",
        )
