import os
from typing import cast

import anthropic as _anthropic
from anthropic.types import TextBlock

_SUMMARIZE_PROMPT = (
    "Summarise the following Indian stock market corporate announcement in 2-3 concise "
    "sentences. Focus on the key business impact.\n\n{text}"
)
_CLASSIFY_PROMPT = (
    "Classify the following corporate announcement into exactly one of these categories: "
    "{categories}. Reply with only the category name, nothing else.\n\nAnnouncement:\n{text}"
)


class AnthropicProvider:
    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-7"):
        self._client = _anthropic.AsyncAnthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        self._model = model

    async def summarize(self, text: str) -> str:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=256,
            messages=[{"role": "user", "content": _SUMMARIZE_PROMPT.format(text=text)}],
        )
        return cast(TextBlock, message.content[0]).text.strip()

    async def classify(self, text: str, categories: list[str]) -> str:
        cats = ", ".join(categories)
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=32,
            messages=[
                {
                    "role": "user",
                    "content": _CLASSIFY_PROMPT.format(categories=cats, text=text),
                }
            ],
        )
        return cast(TextBlock, message.content[0]).text.strip()
