import os

from google import genai

_SUMMARIZE_PROMPT = (
    "Summarise the following Indian stock market corporate announcement in 2-3 concise "
    "sentences. Focus on the key business impact.\n\n{text}"
)
_CLASSIFY_PROMPT = (
    "Classify the following corporate announcement into exactly one of these categories: "
    "{categories}. Reply with only the category name, nothing else.\n\nAnnouncement:\n{text}"
)


class GeminiProvider:
    def __init__(self, api_key: str | None = None, model: str = "gemma-4-31b-it"):
        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
        self._model = model

    async def summarize(self, text: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=_SUMMARIZE_PROMPT.format(text=text),
        )
        return response.text.strip()

    async def classify(self, text: str, categories: list[str]) -> str:
        cats = ", ".join(categories)
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=_CLASSIFY_PROMPT.format(categories=cats, text=text),
        )
        return response.text.strip()
