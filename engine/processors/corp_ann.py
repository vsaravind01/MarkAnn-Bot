import asyncio
import base64
import json
import logging
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from functools import partial

import pytz
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Announcement
from database.redis import (
    alert_channel,
    dedup_key,
    inflight_key,
    result_key,
    seconds_until_midnight,
)
from engine.events import push_event
from engine.processors.base import ProcessorBase
from engine.processors.pdf import extract_pdf_text, render_pdf_pages
from engine.session import NseSession
from llm.provider import (
    AnnouncementAnalysis,
    AnnouncementPageImage,
    LLMContextWindowError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseFormatError,
)

logger = logging.getLogger(__name__)

# Gemini's limit is 262 144 tokens; ~4 chars/token gives ~1 M chars.
# We cap well below that to leave headroom for prompt overhead.
_MAX_TEXT_CHARS = 200_000
_INITIAL_BATCH_SIZE = 5
_DEFAULT_FOLLOW_UP_BATCH_SIZE = 5
_LARGE_DOC_FOLLOW_UP_BATCH_SIZE = 10
_LARGE_DOC_THRESHOLD_PAGES = 15
_CONTEXT_BATCH_SHRINK_FACTOR = 0.8
_RENDER_MAX_DIMENSION_PX = 900
_RENDER_JPEG_QUALITY = 60

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
_DEFAULT_ANNOUNCED_AT = datetime(2000, 1, 1, 0, 0, 0)
_PROCESSING_MODE_MULTIMODAL = "multimodal"
_PROCESSING_MODE_TEXT = "text"


class InputSchema(BaseModel):
    """Fields the corp_ann processor requires from its poller."""

    seq_id: str
    symbol: str
    sm_name: str
    attchmntFile: str
    attchmntText: str
    an_dt: str


def _parse_nse_datetime(dt_str: str | None, *, default: datetime) -> datetime:
    if not isinstance(dt_str, str):
        logger.warning("Invalid NSE datetime value %r; using default timestamp", dt_str)
        return default

    try:
        naive = datetime.strptime(dt_str, "%d-%b-%Y %H:%M:%S")
    except ValueError:
        logger.warning("Malformed NSE datetime %r; using default timestamp", dt_str)
        return default

    return _IST.localize(naive).replace(tzinfo=None)


def _should_release_dedup_key_after_error(
    exc: Exception, *, post_commit_cache_or_publish: bool
) -> bool:
    _ = exc
    _ = post_commit_cache_or_publish
    # Exceptions before DB commit should be retry-eligible by default.
    # Exceptions after commit (cache/publish) are also retry-eligible.
    return True


class CorporateAnnouncementsProcessor(ProcessorBase):
    @classmethod
    def default_config(cls) -> dict:
        return {"pool_size": 8}

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

    async def process(self, item: dict) -> str | None:
        seq_id = item.get("seq_id", "")
        symbol = item.get("symbol", "")
        dedup_redis_key = dedup_key("corp_ann", seq_id)
        inflight_redis_key = inflight_key("corp_ann", seq_id)

        acquired = await self._redis.set(dedup_redis_key, "1", nx=True, ex=172800)
        if not acquired:
            logger.debug(f"Skipping duplicate seq_id={seq_id}")
            return

        post_commit_cache_or_publish = False

        try:
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
                    self._redis,
                    "warn",
                    f"skipped seq_id={seq_id} ({symbol}): attachment not a PDF",
                    api="corp_ann",
                )
                await self._redis.delete(dedup_redis_key)
                return
            pdf_bytes = response.content

            loop = asyncio.get_running_loop()
            announced_at = _parse_nse_datetime(item.get("an_dt"), default=_DEFAULT_ANNOUNCED_AT)
            company = item.get("sm_name", "")
            announcement_text = item.get("attchmntText", "")
            analysis, processing_mode = await self._analyze_with_multimodal_fallback(
                seq_id=seq_id,
                symbol=symbol,
                company=company,
                announcement_text=announcement_text,
                pdf_bytes=pdf_bytes,
                loop=loop,
            )
            summary = analysis.summary
            category = analysis.category

            ann = await self._db.get(Announcement, seq_id)
            if ann is None:
                ann = Announcement(
                    seq_id=seq_id,
                    symbol=symbol,
                    company=company,
                    category=category,
                    announcement_text=announcement_text,
                    summary=summary,
                    processing_mode=processing_mode,
                    attachment_url=attachment_url,
                    announced_at=announced_at,
                )
                self._db.add(ann)
            else:
                ann.symbol = symbol
                ann.company = company
                ann.category = category
                ann.announcement_text = announcement_text
                ann.summary = summary
                ann.processing_mode = processing_mode
                ann.attachment_url = attachment_url
                ann.announced_at = announced_at
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

            post_commit_cache_or_publish = True
            await self._redis.set(
                result_key(symbol, seq_id),
                payload_json,
                ex=seconds_until_midnight(),
            )
            await self._redis.publish(alert_channel(symbol), payload_json)

            logger.info(
                f"Processed announcement seq_id={seq_id} symbol={symbol} category={category}"
            )
            # The engine wrapper logs the success event with the processing time;
            # return a summary describing what was processed.
            return f"{symbol} ({company}) — {category}"
        except Exception as exc:
            if _should_release_dedup_key_after_error(
                exc, post_commit_cache_or_publish=post_commit_cache_or_publish
            ):
                # Always release the dedup key so a retry can re-process. Also
                # release the inflight guard UNLESS the consumer re-queues the item
                # itself (rate-limit path) — otherwise a failed item stays stuck
                # until the inflight TTL expires (e.g. the LLM provider was down and
                # later recovered), blocking the poller from re-enqueuing it.
                keys_to_release = [dedup_redis_key]
                if not isinstance(exc, LLMRateLimitError):
                    keys_to_release.append(inflight_redis_key)
                try:
                    await self._redis.delete(*keys_to_release)
                except Exception:
                    logger.exception(
                        "Failed to release dedup/inflight keys for seq_id=%s after error",
                        seq_id,
                    )
            raise

    async def _analyze_with_multimodal_fallback(
        self,
        *,
        seq_id: str,
        symbol: str,
        company: str,
        announcement_text: str,
        pdf_bytes: bytes,
        loop: asyncio.AbstractEventLoop,
    ) -> tuple[AnnouncementAnalysis, str]:
        try:
            analysis = await self._analyze_multimodal(
                symbol=symbol,
                company=company,
                announcement_text=announcement_text,
                pdf_bytes=pdf_bytes,
                loop=loop,
            )
            return analysis, _PROCESSING_MODE_MULTIMODAL
        except LLMRateLimitError:
            raise  # both paths share the same API; text fallback would also be rate-limited
        except LLMProviderError as exc:
            logger.warning(
                "seq_id=%s multimodal analysis failed, falling back to text analysis: %s",
                seq_id,
                exc,
            )
            await push_event(
                self._redis,
                "warn",
                f"seq_id={seq_id} ({symbol}): multimodal analysis failed, using text fallback",
                api="corp_ann",
            )
            analysis = await self._analyze_text_fallback(
                seq_id=seq_id,
                symbol=symbol,
                company=company,
                announcement_text=announcement_text,
                pdf_bytes=pdf_bytes,
                loop=loop,
            )
            return analysis, _PROCESSING_MODE_TEXT

    async def _analyze_multimodal(
        self,
        *,
        symbol: str,
        company: str,
        announcement_text: str,
        pdf_bytes: bytes,
        loop: asyncio.AbstractEventLoop,
    ) -> AnnouncementAnalysis:
        start_page = 1
        current_batch_size = _INITIAL_BATCH_SIZE
        provisional_summary: str | None = None
        final_analysis: AnnouncementAnalysis | None = None
        follow_up_batch_size = _DEFAULT_FOLLOW_UP_BATCH_SIZE

        while True:
            while True:
                rendered_pages = await loop.run_in_executor(
                    self._process_pool,
                    partial(
                        render_pdf_pages,
                        pdf_bytes,
                        start_page=start_page,
                        end_page=start_page + current_batch_size - 1,
                        max_dimension_px=_RENDER_MAX_DIMENSION_PX,
                        jpeg_quality=_RENDER_JPEG_QUALITY,
                    ),
                )
                page_images = [
                    AnnouncementPageImage(
                        page_number=page.page_number,
                        mime_type=page.media_type,
                        data_base64=base64.b64encode(page.image_bytes).decode("ascii"),
                    )
                    for page in rendered_pages.pages
                ]
                if not rendered_pages.pages:
                    raise LLMProviderError(
                        "No pages were rendered from PDF for multimodal analysis "
                        f"(start_page={start_page}, batch_size={current_batch_size}, "
                        f"total_pages={rendered_pages.total_pages})"
                    )
                page_range_end = rendered_pages.pages[-1].page_number
                follow_up_batch_size = (
                    _LARGE_DOC_FOLLOW_UP_BATCH_SIZE
                    if rendered_pages.total_pages > _LARGE_DOC_THRESHOLD_PAGES
                    else _DEFAULT_FOLLOW_UP_BATCH_SIZE
                )

                try:
                    analysis = await self._analyze_multimodal_pass_with_format_retry(
                        page_images=page_images,
                        symbol=symbol,
                        company=company,
                        announcement_text=announcement_text,
                        page_range_start=start_page,
                        page_range_end=page_range_end,
                        total_pages=rendered_pages.total_pages,
                        provisional_summary=provisional_summary,
                    )
                    break
                except LLMContextWindowError as exc:
                    shrunk_batch_size = max(
                        1,
                        int(current_batch_size * _CONTEXT_BATCH_SHRINK_FACTOR),
                    )
                    if shrunk_batch_size == current_batch_size:
                        raise exc
                    logger.warning(
                        "Multimodal context window exceeded for pages %s-%s; shrinking batch %s -> %s",
                        start_page,
                        page_range_end,
                        current_batch_size,
                        shrunk_batch_size,
                    )
                    current_batch_size = shrunk_batch_size

            final_analysis = analysis
            provisional_summary = analysis.summary
            unseen_pages_remain = page_range_end < rendered_pages.total_pages
            if not unseen_pages_remain:
                break
            if analysis.need_more_pages is not True:
                break

            start_page = page_range_end + 1
            current_batch_size = follow_up_batch_size

        if final_analysis is None:
            raise RuntimeError("No announcement analysis generated from multimodal flow.")
        return final_analysis

    async def _analyze_multimodal_pass_with_format_retry(
        self,
        *,
        page_images: list[AnnouncementPageImage],
        symbol: str,
        company: str,
        announcement_text: str,
        page_range_start: int,
        page_range_end: int,
        total_pages: int,
        provisional_summary: str | None,
    ) -> AnnouncementAnalysis:
        try:
            return await self._llm.analyze_announcement(
                page_images=page_images,
                categories=ANNOUNCEMENT_CATEGORIES,
                symbol=symbol,
                company=company,
                announcement_text=announcement_text,
                page_range_start=page_range_start,
                page_range_end=page_range_end,
                total_pages=total_pages,
                provisional_summary=provisional_summary,
                response_format_retry=False,
            )
        except LLMResponseFormatError:
            return await self._llm.analyze_announcement(
                page_images=page_images,
                categories=ANNOUNCEMENT_CATEGORIES,
                symbol=symbol,
                company=company,
                announcement_text=announcement_text,
                page_range_start=page_range_start,
                page_range_end=page_range_end,
                total_pages=total_pages,
                provisional_summary=provisional_summary,
                response_format_retry=True,
            )

    async def _analyze_text_fallback(
        self,
        *,
        seq_id: str,
        symbol: str,
        company: str,
        announcement_text: str,
        pdf_bytes: bytes,
        loop: asyncio.AbstractEventLoop,
    ) -> AnnouncementAnalysis:
        text = await loop.run_in_executor(self._process_pool, extract_pdf_text, pdf_bytes)

        if len(text) > _MAX_TEXT_CHARS:
            logger.warning(
                f"seq_id={seq_id} PDF text truncated "
                f"({len(text)} → {_MAX_TEXT_CHARS} chars) before LLM"
            )
            await push_event(
                self._redis,
                "warn",
                f"seq_id={seq_id} ({symbol}): PDF truncated {len(text):,} → {_MAX_TEXT_CHARS:,} chars",
                api="corp_ann",
            )
            text = text[:_MAX_TEXT_CHARS]

        try:
            return await self._llm.analyze_text_announcement(
                text=text,
                categories=ANNOUNCEMENT_CATEGORIES,
                symbol=symbol,
                company=company,
                announcement_text=announcement_text,
                response_format_retry=False,
            )
        except LLMResponseFormatError:
            return await self._llm.analyze_text_announcement(
                text=text,
                categories=ANNOUNCEMENT_CATEGORIES,
                symbol=symbol,
                company=company,
                announcement_text=announcement_text,
                response_format_retry=True,
            )


Processor = CorporateAnnouncementsProcessor
