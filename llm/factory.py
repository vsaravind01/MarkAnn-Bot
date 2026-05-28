import os

from llm.provider import LLMProvider


def get_provider() -> LLMProvider:
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        from llm.openai import OpenAIProvider
        return OpenAIProvider()
    if provider == "anthropic":
        from llm.anthropic import AnthropicProvider
        return AnthropicProvider()
    if provider == "gemini":
        from llm.gemini import GeminiProvider
        return GeminiProvider()
    raise ValueError(f"Unknown LLM_PROVIDER={provider!r}. Choose: openai | anthropic | gemini")
