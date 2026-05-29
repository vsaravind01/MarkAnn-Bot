from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm.anthropic import AnthropicProvider
from llm.factory import get_provider
from llm.gemini import GeminiProvider
from llm.openai import OpenAIProvider


async def test_openai_summarize():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Strong quarterly growth."
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        result = await provider.summarize("Infosys reports Q4 results...")
    assert result == "Strong quarterly growth."


async def test_openai_classify():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "financial_results"
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        result = await provider.classify("Q4 results...", ["financial_results", "acquisition"])
    assert result == "financial_results"


async def test_anthropic_summarize():
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = "Acquisition of XYZ Corp."
    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        result = await provider.summarize("Infosys acquires XYZ...")
    assert result == "Acquisition of XYZ Corp."


async def test_gemini_summarize():
    mock_response = MagicMock()
    mock_response.text = "New product launched."
    with patch("llm.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client
        provider = GeminiProvider(api_key="test-key")
        result = await provider.summarize("Launch of new product...")
    assert result == "New product launched."


def test_factory_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = get_provider()
    assert isinstance(provider, OpenAIProvider)


def test_factory_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    provider = get_provider()
    assert isinstance(provider, AnthropicProvider)


def test_factory_gemini(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-test")
    provider = get_provider()
    assert isinstance(provider, GeminiProvider)


def test_factory_invalid(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_provider()
