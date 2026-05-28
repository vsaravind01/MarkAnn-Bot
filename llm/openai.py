import os

from openai import AsyncOpenAI

_SUMMARIZE_SYSTEM = (
    "You are a financial analyst. Summarise the following Indian stock market corporate "
    "announcement in 2-3 concise sentences. Focus on the key business impact."
)
_CLASSIFY_SYSTEM = (
    "You are a financial analyst. Classify the following corporate announcement into exactly "
    "one of the provided categories. Reply with only the category name, nothing else."
)


class OpenAIProvider:
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        self._client = AsyncOpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
        self._model = model

    async def summarize(self, text: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SUMMARIZE_SYSTEM},
                {"role": "user", "content": text},
            ],
            max_tokens=256,
        )
        return response.choices[0].message.content.strip()

    async def classify(self, text: str, categories: list[str]) -> str:
        cats = ", ".join(categories)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _CLASSIFY_SYSTEM},
                {"role": "user", "content": f"Categories: {cats}\n\nAnnouncement:\n{text}"},
            ],
            max_tokens=32,
        )
        return response.choices[0].message.content.strip()
