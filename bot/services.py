import asyncio
import logging
import os
import traceback

from telegram import Update

from bot import decorators, utils
from bot.constants import LIVE_STARTED_MESSAGE
from channels import ai_engine, ann_channel
from database import memory_cache, user_db, vector_db

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

db = vector_db.VectorDB(url=QDRANT_URL, api_key=QDRANT_API_KEY)
user_db = user_db.UserDB(db_url="sqlite:///./bot/logs/user.db")


@decorators.service_logger(service_name="Startup Service")
def startup_service():
    if db.create_collection_if_not_exists(collection_name="market_announcements"):
        logger.info("Collection Created - market_announcements")


@decorators.service_logger(service_name="Announcement Service")
async def ann_service(update: Update, client_id: str, stop_event: asyncio.Event):
    """Service to fetch and send announcements to the user.

    Args:
    -----
    update: Update
        Telegram Update object
    client_id: str
        Telegram User ID
    stop_event: asyncio.Event
        Event to stop the service

    Raises
    ------
    Exception
        If an error occurs during the service
    """
    channel = ann_channel.BseChannel(
        category="Company Update",
        subcategory="Press Release / Media Release",
        n_items=10,
        frequency=1,
    )
    engine = ai_engine.AIEngine(channel=channel, db=db)
    cache = memory_cache.MemoryCache(user=update.effective_user, db=user_db)
    await update.effective_chat.send_message(text=LIVE_STARTED_MESSAGE)

    try:
        while not stop_event.is_set() and asyncio.get_event_loop().is_running():
            data = channel.fetch()

            if not data:
                logger.info(f"AnnService - No Data - BSE - Client ID: {client_id}")
                await asyncio.sleep(channel.frequency * 60)
                continue

            # Remove items that have already been sent and
            # filter the ids of the remaining items
            data = [item for item in data if item["id"] not in cache]
            ids = [item["id"] for item in data]
            for item in db.get_data_by_ids(ids=ids):
                message = utils.format_message(item.payload)
                await update.effective_chat.send_message(
                    text=message, parse_mode="MarkdownV2"
                )
                cache.add(item.payload["id"])
                logger.info(
                    f"AnnService - Message Sent - BSE - Client ID: {client_id} - Point ID: {item.payload['id']}"
                )

            data = [item for item in data if item["id"] not in cache]
            for item in data:
                text = channel.get_pdf_text(item["attachment"])
                summary = engine.summarize_text(text)
                if summary is None:
                    logger.info(
                        f"AnnService - Summary Already Exists - BSE - Client ID: {client_id}"
                    )
                    continue
                item["summary"] = summary
                message = utils.format_message(item)
                await update.effective_chat.send_message(
                    text=message, parse_mode="MarkdownV2"
                )
                cache.add(item["id"])
                pt_id = db.insert_data(
                    text, item, collection_name="market_announcements"
                )
                logger.info(
                    f"AnnService - Message Sent - BSE - Client ID: {client_id} - Point ID: {pt_id}"
                )
                await asyncio.sleep(1)
            await asyncio.sleep(channel.frequency * 60)
    except Exception:
        traceback.print_exc()
        logger.error(f"AnnService - Error - BSE - Client ID: {client_id}")
        raise
