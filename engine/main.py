import asyncio
import logging
import os
from concurrent.futures import ProcessPoolExecutor

from sqlalchemy import select

from database.models import EngineConfig
from database.redis import get_redis_client
from database.session import AsyncSessionLocal
from engine.consumer import ConsumerPool
from engine.pollers.corp_ann import CorporateAnnouncementsPoller
from engine.processor.corp_ann import CorporateAnnouncementsProcessor
from engine.session import NseSession
from engine.supervisor import Supervisor, Watchdog
from llm.factory import get_provider

logger = logging.getLogger(__name__)

_BASE_INTERVAL = float(os.environ.get("POLL_INTERVAL", "5"))
_SILENCE_THRESHOLD = float(os.environ.get("POLLER_SILENCE_THRESHOLD", "600"))


async def _get_pool_size(api: str, env_var: str, default: int) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EngineConfig).where(EngineConfig.key == f"pool_size:{api}")
        )
        config = result.scalar_one_or_none()
    if config:
        return int(config.value)
    return int(os.environ.get(env_var, str(default)))


async def run() -> None:
    redis = get_redis_client()
    llm = get_provider()
    process_pool = ProcessPoolExecutor(max_workers=os.cpu_count())
    supervisor = Supervisor(restart_delay=2.0)

    corp_ann_pool_size = await _get_pool_size("corp_ann", "CONSUMER_POOL_SIZE_CORP_ANN", 8)

    async with NseSession() as session:
        corp_ann_queue: asyncio.Queue = asyncio.Queue()

        async def start_corp_ann_poller() -> None:
            poller = CorporateAnnouncementsPoller(
                queue=corp_ann_queue,
                session=session,
                redis=redis,
                base_interval=_BASE_INTERVAL,
            )
            await poller.run()

        async def corp_ann_processor_fn(item: dict) -> None:
            async with AsyncSessionLocal() as db:
                processor = CorporateAnnouncementsProcessor(
                    redis=redis,
                    db=db,
                    llm=llm,
                    process_pool=process_pool,
                )
                await processor.process(item)

        supervisor.register("corp_ann_poller", start_corp_ann_poller)

        corp_ann_pool = ConsumerPool(
            queue=corp_ann_queue,
            processor_fn=corp_ann_processor_fn,
            size=corp_ann_pool_size,
        )
        await corp_ann_pool.start()

        watchdog = Watchdog(
            redis=redis,
            supervisor=supervisor,
            silence_threshold=_SILENCE_THRESHOLD,
        )
        watchdog.register("corp_ann_poller")

        await supervisor.start_all()
        try:
            await asyncio.gather(watchdog.run(), return_exceptions=True)
        finally:
            await supervisor.shutdown()
            await corp_ann_pool.stop()

    process_pool.shutdown(wait=False)
    await redis.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
