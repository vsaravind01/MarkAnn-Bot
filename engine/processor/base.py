from typing import Protocol


class Processor(Protocol):
    async def process(self, item: dict) -> None: ...
