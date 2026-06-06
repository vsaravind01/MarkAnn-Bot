from abc import ABC, abstractmethod
from typing import Protocol


class Processor(Protocol):
    async def process(self, item: dict) -> None: ...


class ProcessorBase(ABC):
    """Base class for registry-managed processors."""

    @classmethod
    def default_config(cls) -> dict:
        return {}

    @abstractmethod
    async def process(self, item: dict) -> None: ...
