import asyncio
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor

from database.redis import get_redis_client, queue_key
from database.session import AsyncSessionLocal
from engine.consumer import ConsumerPool
from engine.events import push_event
from engine.health import write_processor_status, write_status
from engine.registry import load_enabled
from engine.session import NseSession
from engine.supervisor import Supervisor, Watchdog
from llm.factory import get_provider

logger = logging.getLogger(__name__)

_SILENCE_THRESHOLD = float(os.environ.get("POLLER_SILENCE_THRESHOLD", "600"))


async def _run_processor(processor, item: dict, *, redis, api: str) -> None:
    """Run one item through a processor, recording the processing time.

    Applies to every processor: when ``process`` reports real work (a non-None
    summary) the elapsed wall-clock time is written to the event log.
    """
    start = time.perf_counter()
    summary = await processor.process(item)
    if summary is not None:
        elapsed = time.perf_counter() - start
        await push_event(redis, "ok", f"processed {summary} in {elapsed:.2f}s", api=api)


async def build_components(
    *,
    db,
    supervisor: Supervisor,
    redis,
    session,
    llm,
    process_pool,
    db_factory,
    watchdog_register,
) -> list[ConsumerPool]:
    """Load enabled registry rows and register them with the supervisor."""
    loaded_pollers, loaded_processors = await load_enabled(db)
    pools: list[ConsumerPool] = []

    for loaded_poller in loaded_pollers:
        def make_poller_starter(loaded):
            async def _start() -> None:
                poller = loaded.poller_cls(
                    session=session,
                    redis=redis,
                    **loaded.config,
                )
                await poller.run()

            return _start

        supervisor.register(
            f"poller:{loaded_poller.api_name}",
            make_poller_starter(loaded_poller),
        )
        watchdog_register(loaded_poller.api_name)

    for loaded_processor in loaded_processors:
        primary_poller_api = loaded_processor.poller_api_names[0]
        pool_size = int(loaded_processor.config.get("pool_size", 8))

        def make_processor_fn(loaded):
            async def _fn(item: dict) -> None:
                async with db_factory() as proc_db:
                    processor = loaded.processor_cls(
                        redis=redis,
                        db=proc_db,
                        llm=llm,
                        process_pool=process_pool,
                        session=session,
                    )
                    await _run_processor(processor, item, redis=redis, api=loaded.api_name)

            return _fn

        pool = ConsumerPool(
            redis=redis,
            queue_key=queue_key(primary_poller_api),
            processor_fn=make_processor_fn(loaded_processor),
            size=pool_size,
        )
        pools.append(pool)

        def make_processor_starter(p: ConsumerPool, api: str):
            async def _start() -> None:
                await write_processor_status(redis, api, "running")
                await p.run()

            return _start

        supervisor.register(
            f"processor:{loaded_processor.api_name}",
            make_processor_starter(pool, loaded_processor.api_name),
        )

    return pools


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
        component = cmd.get("component")
        if component is None:
            api_field = cmd.get("api")
            if api_field:
                component = f"poller:{api_field}"
        action = cmd.get("action")
        if not component or not action:
            continue
        try:
            if action == "pause":
                await supervisor.pause(component)
                api = component.split(":", 1)[-1]
                if component.startswith("poller:"):
                    await write_status(redis, api, "paused")
                elif component.startswith("processor:"):
                    await write_processor_status(redis, api, "paused")
                logger.info("Control: paused %r", component)
                await push_event(redis, "info", "paused by operator", api=api)
            elif action == "resume":
                await supervisor.start(component)
                api = component.split(":", 1)[-1]
                if component.startswith("poller:"):
                    await write_status(redis, api, "running")
                elif component.startswith("processor:"):
                    await write_processor_status(redis, api, "running")
                logger.info("Control: resumed %r", component)
                await push_event(redis, "info", "resumed by operator", api=api)
            elif action == "restart":
                await supervisor.restart(component)
                api = component.split(":", 1)[-1]
                logger.info("Control: restarted %r", component)
                await push_event(redis, "info", "restarted by operator", api=api)
            else:
                logger.warning("Control: unknown action %r for %r", action, component)
        except Exception:
            logger.exception("Control: error handling %r for %r", action, component)


async def run() -> None:
    redis = get_redis_client()
    llm = get_provider()
    process_pool = ProcessPoolExecutor(max_workers=os.cpu_count())
    supervisor = Supervisor(restart_delay=2.0)

    async with NseSession() as session:
        watchdog = Watchdog(
            redis=redis,
            supervisor=supervisor,
            silence_threshold=_SILENCE_THRESHOLD,
        )
        async with AsyncSessionLocal() as db:
            pools = await build_components(
                db=db,
                supervisor=supervisor,
                redis=redis,
                session=session,
                llm=llm,
                process_pool=process_pool,
                db_factory=AsyncSessionLocal,
                watchdog_register=watchdog.register,
            )

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
            for pool in pools:
                await pool.stop()

    process_pool.shutdown(wait=False)
    await redis.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
