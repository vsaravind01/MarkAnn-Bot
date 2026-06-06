"""Discovery, schema validation, and DB resolution for component registry."""

import importlib
import json
import logging
from dataclasses import dataclass

from sqlalchemy import select

from database.models import PollerConfig, ProcessorConfig, ProcessorPollerLink

logger = logging.getLogger(__name__)


class ContractError(Exception):
    """Raised when a module does not satisfy the poller/processor contract."""


class SchemaIncompatibleError(Exception):
    """Raised when a processor's input schema is not satisfied by a poller's output."""


@dataclass
class PollerModuleInfo:
    api_name: str
    module: str
    poller_cls: type
    output_schema: dict
    default_config: dict


@dataclass
class ProcessorModuleInfo:
    api_name: str
    module: str
    processor_cls: type
    input_schema: dict
    default_config: dict


@dataclass
class LoadedPoller:
    api_name: str
    poller_cls: type
    config: dict


@dataclass
class LoadedProcessor:
    api_name: str
    processor_cls: type
    config: dict
    poller_api_names: list[str]


def schema_incompatibilities(input_schema: dict, output_schema: dict) -> list[str]:
    """Return incompatibility messages; empty list means compatible."""
    errors: list[str] = []
    in_props = input_schema.get("properties", {})
    out_props = output_schema.get("properties", {})
    for field, in_spec in in_props.items():
        if field not in out_props:
            in_type = in_spec.get("type", "any")
            errors.append(f"field {field!r} ({in_type}) not present in output schema")
            continue
        in_type = in_spec.get("type")
        out_type = out_props[field].get("type")
        if in_type and out_type and in_type != out_type:
            errors.append(
                f"field {field!r} expects type {in_type!r} but output emits {out_type!r}"
            )
    return errors


def api_name_from_module(module_path: str) -> str:
    return module_path.rsplit(".", 1)[-1]


def _default_config(obj: type) -> dict:
    fn = getattr(obj, "default_config", None)
    if fn is None:
        return {}
    return fn()


def load_poller_module(module_path: str) -> PollerModuleInfo:
    mod = importlib.import_module(module_path)
    if not hasattr(mod, "OutputSchema"):
        raise ContractError(f"{module_path!r} is missing required name 'OutputSchema'")
    if not hasattr(mod, "Poller"):
        raise ContractError(f"{module_path!r} is missing required name 'Poller'")
    return PollerModuleInfo(
        api_name=api_name_from_module(module_path),
        module=module_path,
        poller_cls=mod.Poller,
        output_schema=mod.OutputSchema.model_json_schema(),
        default_config=_default_config(mod.Poller),
    )


def load_processor_module(module_path: str) -> ProcessorModuleInfo:
    mod = importlib.import_module(module_path)
    if not hasattr(mod, "InputSchema"):
        raise ContractError(f"{module_path!r} is missing required name 'InputSchema'")
    if not hasattr(mod, "Processor"):
        raise ContractError(f"{module_path!r} is missing required name 'Processor'")
    return ProcessorModuleInfo(
        api_name=api_name_from_module(module_path),
        module=module_path,
        processor_cls=mod.Processor,
        input_schema=mod.InputSchema.model_json_schema(),
        default_config=_default_config(mod.Processor),
    )


def _merge_config(defaults: dict, override_json: str) -> dict:
    merged = dict(defaults)
    try:
        merged.update(json.loads(override_json or "{}"))
    except json.JSONDecodeError:
        logger.warning("Invalid config JSON %r; using defaults only", override_json)
    return merged


async def load_enabled(db) -> tuple[list[LoadedPoller], list[LoadedProcessor]]:
    """Load enabled registry rows, skipping broken components with a log."""
    poller_rows = (
        await db.execute(select(PollerConfig).where(PollerConfig.enabled.is_(True)))
    ).scalars().all()
    processor_rows = (
        await db.execute(select(ProcessorConfig).where(ProcessorConfig.enabled.is_(True)))
    ).scalars().all()
    link_rows = (await db.execute(select(ProcessorPollerLink))).scalars().all()
    all_poller_rows = (await db.execute(select(PollerConfig))).scalars().all()

    poller_id_to_api = {row.id: row.api_name for row in all_poller_rows}
    poller_row_by_api = {row.api_name: row for row in poller_rows}

    loaded_pollers: list[LoadedPoller] = []
    enabled_poller_apis: set[str] = set()
    for row in poller_rows:
        try:
            info = load_poller_module(row.module)
        except Exception as exc:  # noqa: BLE001 - startup deliberately skips bad rows
            logger.error("Skipping poller %r: %s", row.api_name, exc)
            continue
        loaded_pollers.append(
            LoadedPoller(
                api_name=row.api_name,
                poller_cls=info.poller_cls,
                config=_merge_config(info.default_config, row.config),
            )
        )
        enabled_poller_apis.add(row.api_name)

    links_by_processor: dict[int, list[int]] = {}
    for link in link_rows:
        links_by_processor.setdefault(link.processor_id, []).append(link.poller_id)

    loaded_processors: list[LoadedProcessor] = []
    for row in processor_rows:
        linked_poller_ids = links_by_processor.get(row.id, [])
        linked_apis = [poller_id_to_api.get(pid) for pid in linked_poller_ids]
        if not linked_apis or any(api is None for api in linked_apis):
            logger.error("Skipping processor %r: missing poller link", row.api_name)
            continue
        if any(api not in enabled_poller_apis for api in linked_apis):
            logger.error(
                "Skipping processor %r: linked poller(s) not enabled/loaded", row.api_name
            )
            continue
        try:
            info = load_processor_module(row.module)
        except Exception as exc:  # noqa: BLE001 - startup deliberately skips bad rows
            logger.error("Skipping processor %r: %s", row.api_name, exc)
            continue

        incompatible = False
        for api in linked_apis:
            poller_row = poller_row_by_api[api]
            try:
                out_schema = json.loads(poller_row.output_schema or "{}")
            except json.JSONDecodeError:
                logger.error(
                    "Skipping processor %r: invalid output schema for poller %r",
                    row.api_name,
                    api,
                )
                incompatible = True
                break
            errors = schema_incompatibilities(info.input_schema, out_schema)
            if errors:
                logger.error(
                    "Skipping processor %r: schema incompatible with poller %r: %s",
                    row.api_name,
                    api,
                    "; ".join(errors),
                )
                incompatible = True
                break
        if incompatible:
            continue

        loaded_processors.append(
            LoadedProcessor(
                api_name=row.api_name,
                processor_cls=info.processor_cls,
                config=_merge_config(info.default_config, row.config),
                poller_api_names=[api for api in linked_apis if api is not None],
            )
        )

    return loaded_pollers, loaded_processors
