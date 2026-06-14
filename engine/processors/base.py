from abc import ABC, abstractmethod
from typing import Protocol


class Processor(Protocol):
    async def process(self, item: dict) -> str | None: ...


class ProcessorBase(ABC):
    """Base class for registry-managed processors."""

    @classmethod
    def default_config(cls) -> dict:
        return {}

    @abstractmethod
    async def process(self, item: dict) -> str | None:
        """Process one item.

        Return a short human summary when real work was done — the engine logs it
        to the event log together with the processing time — or ``None`` when the
        item was skipped (duplicate, unsupported, etc.) so nothing is logged.
        """
