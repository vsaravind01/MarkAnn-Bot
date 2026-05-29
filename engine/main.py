import asyncio
import json
import logging
import os
from concurrent.futures import ProcessPoolExecutor

from sqlalchemy import select

from database.models import EngineConfig
from database.redis import get_redis_client
from database.session import AsyncSessionLocal
from engine.consumer import ConsumerPool
from engine.health import write_status
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


async def _listen_control(redis, supervisor: Supervisor) -> None:
    """Subscribe to engine:control and handle pause/resume/restart commands."""
    pubsub = redis.pubsub()
    await pubsub.subscribe("engine:control")
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            cmd = json.loads(message["data"])
        except (json.JSONDecodeError, TypeError):
            continue
        api = cmd.get("api")
        action = cmd.get("action")
        if not api or not action:
            continue
        try:
            if action == "pause":
                await supervisor.pause(api)
                await write_status(redis, api, "paused")
                logger.info(f"Control: paused {api!r}")
            elif action == "resume":
                await supervisor.start(api)
                logger.info(f"Control: resumed {api!r}")
            elif action == "restart":
                await supervisor.restart(api)
                logger.info(f"Control: restarted {api!r}")
            else:
                logger.warning(f"Control: unknown action {action!r} for {api!r}")
        except Exception:
            logger.exception(f"Control: error handling {action!r} for {api!r}")


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
                    session=session,
                )
                await processor.process(item)

        supervisor.register("corp_ann", start_corp_ann_poller)

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
        watchdog.register("corp_ann")

        await supervisor.start_all()
        try:
            results = await asyncio.gather(
                watchdog.run(),
                _listen_control(redis, supervisor),
                return_exceptions=True,
            )
            for exc in results:
                if isinstance(exc, BaseException):
                    logger.error("Background task exited unexpectedly", exc_info=exc)
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
