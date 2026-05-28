from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    async def summarize(self, text: str) -> str: ...
    async def classify(self, text: str, categories: list[str]) -> str: ...
