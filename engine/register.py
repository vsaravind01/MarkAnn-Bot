"""CLI to register pollers/processors into the DB registry."""

import argparse
import asyncio
import json
import logging
import sys

from sqlalchemy import select

from database.models import PollerConfig, ProcessorConfig, ProcessorPollerLink
from database.session import AsyncSessionLocal
from engine.registry import (
    ContractError,
    load_poller_module,
    load_processor_module,
    schema_incompatibilities,
)

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="engine.register")
    sub = parser.add_subparsers(dest="command", required=True)

    poller = sub.add_parser("poller", help="Register a poller module")
    poller.add_argument("module")

    processor = sub.add_parser("processor", help="Register a processor module")
    processor.add_argument("module")
    processor.add_argument("--poller", action="append", required=True, dest="pollers")

    enable = sub.add_parser("enable")
    enable.add_argument("kind", choices=["poller", "processor"])
    enable.add_argument("api_name")

    disable = sub.add_parser("disable")
    disable.add_argument("kind", choices=["poller", "processor"])
    disable.add_argument("api_name")

    sub.add_parser("list")
    return parser


async def _register_poller(db, module: str) -> int:
    try:
        info = load_poller_module(module)
    except (ContractError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    existing = (
        await db.execute(select(PollerConfig).where(PollerConfig.module == module))
    ).scalar_one_or_none()
    schema_json = json.dumps(info.output_schema)
    if existing:
        existing.api_name = info.api_name
        existing.output_schema = schema_json
    else:
        db.add(
            PollerConfig(
                module=module,
                api_name=info.api_name,
                output_schema=schema_json,
                config="{}",
                enabled=False,
            )
        )
    await db.commit()
    print(f"registered poller {info.api_name!r} ({module})")
    return 0


async def _register_processor(db, module: str, poller_apis: list[str]) -> int:
    try:
        info = load_processor_module(module)
    except (ContractError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    poller_rows = []
    for api in poller_apis:
        row = (
            await db.execute(select(PollerConfig).where(PollerConfig.api_name == api))
        ).scalar_one_or_none()
        if row is None:
            print(f"error: poller {api!r} is not registered", file=sys.stderr)
            return 1
        poller_rows.append(row)

    for row in poller_rows:
        out_schema = json.loads(row.output_schema or "{}")
        errors = schema_incompatibilities(info.input_schema, out_schema)
        if errors:
            print(
                f"error: processor {info.api_name!r} incompatible with poller "
                f"{row.api_name!r}: {'; '.join(errors)}",
                file=sys.stderr,
            )
            return 1

    existing = (
        await db.execute(select(ProcessorConfig).where(ProcessorConfig.module == module))
    ).scalar_one_or_none()
    schema_json = json.dumps(info.input_schema)
    if existing:
        existing.api_name = info.api_name
        existing.input_schema = schema_json
        processor = existing
    else:
        processor = ProcessorConfig(
            module=module,
            api_name=info.api_name,
            input_schema=schema_json,
            config="{}",
            enabled=False,
        )
        db.add(processor)
    await db.flush()

    existing_links = (
        await db.execute(
            select(ProcessorPollerLink).where(
                ProcessorPollerLink.processor_id == processor.id
            )
        )
    ).scalars().all()
    for link in existing_links:
        await db.delete(link)
    for row in poller_rows:
        db.add(ProcessorPollerLink(processor_id=processor.id, poller_id=row.id))

    await db.commit()
    print(
        f"registered processor {info.api_name!r} ({module}) "
        f"-> pollers {', '.join(poller_apis)}"
    )
    return 0


async def _set_enabled(db, kind: str, api_name: str, value: bool) -> int:
    model = PollerConfig if kind == "poller" else ProcessorConfig
    row = (
        await db.execute(select(model).where(model.api_name == api_name))
    ).scalar_one_or_none()
    if row is None:
        print(f"error: {kind} {api_name!r} is not registered", file=sys.stderr)
        return 1
    row.enabled = value
    await db.commit()
    print(f"{'enabled' if value else 'disabled'} {kind} {api_name!r}")
    return 0


async def _list(db) -> int:
    pollers = (await db.execute(select(PollerConfig))).scalars().all()
    processors = (await db.execute(select(ProcessorConfig))).scalars().all()
    links = (await db.execute(select(ProcessorPollerLink))).scalars().all()
    poller_api_by_id = {poller.id: poller.api_name for poller in pollers}
    links_by_proc: dict[int, list[str]] = {}
    for link in links:
        links_by_proc.setdefault(link.processor_id, []).append(
            poller_api_by_id.get(link.poller_id, "?")
        )

    print("POLLERS:")
    for poller in pollers:
        print(f"  {poller.api_name:20} enabled={poller.enabled}  {poller.module}")
    print("PROCESSORS:")
    for processor in processors:
        linked = ", ".join(links_by_proc.get(processor.id, [])) or "(none)"
        print(
            f"  {processor.api_name:20} enabled={processor.enabled}  "
            f"{processor.module}  <- {linked}"
        )
    return 0


async def run_command(argv: list[str], session_factory) -> int:
    args = _build_parser().parse_args(argv)
    async with session_factory() as db:
        if args.command == "poller":
            return await _register_poller(db, args.module)
        if args.command == "processor":
            return await _register_processor(db, args.module, args.pollers)
        if args.command == "enable":
            return await _set_enabled(db, args.kind, args.api_name, True)
        if args.command == "disable":
            return await _set_enabled(db, args.kind, args.api_name, False)
        if args.command == "list":
            return await _list(db)
    return 2


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    code = asyncio.run(run_command(sys.argv[1:], AsyncSessionLocal))
    sys.exit(code)


if __name__ == "__main__":
    main()
