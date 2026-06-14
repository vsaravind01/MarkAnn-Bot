import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm.anthropic import AnthropicProvider
from llm.factory import get_provider
from llm.gemini import GeminiProvider
from llm.openai import OpenAIProvider
from llm.provider import (
    LLMContextWindowError,
    LLMRateLimitError,
    LLMResponseFormatError,
    parse_analysis_json,
)

_ANALYSIS_JSON = """
{
  "summary": "Infosys reported strong Q4 growth and announced guidance upgrades.",
  "category": "financial_results",
  "confidence": "high",
  "need_more_pages": false
}
"""


def _expected_analyze_announcement_params() -> list[str]:
    return [
        "self",
        "page_images",
        "categories",
        "symbol",
        "company",
        "announcement_text",
        "page_range_start",
        "page_range_end",
        "total_pages",
        "provisional_summary",
        "response_format_retry",
    ]


def _expected_analyze_text_params() -> list[str]:
    return [
        "self",
        "text",
        "categories",
        "symbol",
        "company",
        "announcement_text",
        "response_format_retry",
    ]


def _assert_provider_signature(cls: type[object]) -> None:
    analyze_announcement = inspect.signature(cls.analyze_announcement)
    assert list(analyze_announcement.parameters) == _expected_analyze_announcement_params()
    for name, parameter in analyze_announcement.parameters.items():
        if name == "self":
            continue
        assert parameter.kind == inspect.Parameter.KEYWORD_ONLY
    assert analyze_announcement.parameters["provisional_summary"].default is None
    assert analyze_announcement.parameters["response_format_retry"].default is False

    analyze_text = inspect.signature(cls.analyze_text_announcement)
    assert list(analyze_text.parameters) == _expected_analyze_text_params()
    for name, parameter in analyze_text.parameters.items():
        if name == "self":
            continue
        assert parameter.kind == inspect.Parameter.KEYWORD_ONLY
    assert analyze_text.parameters["response_format_retry"].default is False


def test_parse_analysis_json_accepts_valid_object_json():
    result = parse_analysis_json(
        _ANALYSIS_JSON,
        categories=["financial_results", "acquisition"],
    )
    assert result.category == "financial_results"
    assert result.confidence == "high"
    assert result.need_more_pages is False


def test_parse_analysis_json_rejects_markdown_wrapped_json():
    with pytest.raises(LLMResponseFormatError, match="Model output is not valid JSON"):
        parse_analysis_json(
            f"```json\n{_ANALYSIS_JSON}\n```",
            categories=["financial_results", "acquisition"],
        )


def test_parse_analysis_json_rejects_missing_required_fields():
    with pytest.raises(LLMResponseFormatError, match="Field 'confidence'"):
        parse_analysis_json('{"summary":"x","category":"financial_results"}')


def test_parse_analysis_json_rejects_unknown_category():
    with pytest.raises(LLMResponseFormatError, match="Unknown category"):
        parse_analysis_json(_ANALYSIS_JSON, categories=["acquisition"])


def test_parse_analysis_json_rejects_invalid_confidence():
    with pytest.raises(LLMResponseFormatError, match="Field 'confidence'"):
        parse_analysis_json(
            '{"summary":"x","category":"financial_results","confidence":"certain"}',
            categories=["financial_results"],
        )


def test_parse_analysis_json_rejects_invalid_need_more_pages_type():
    with pytest.raises(LLMResponseFormatError, match="Field 'need_more_pages'"):
        parse_analysis_json(
            '{"summary":"x","category":"financial_results","confidence":"medium","need_more_pages":"yes"}',
            categories=["financial_results"],
        )


def test_provider_signatures_match_contract():
    _assert_provider_signature(OpenAIProvider)
    _assert_provider_signature(AnthropicProvider)
    _assert_provider_signature(GeminiProvider)


async def test_openai_analyze_text_announcement():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = _ANALYSIS_JSON
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        result = await provider.analyze_text_announcement(
            text="Q4 results...",
            categories=["financial_results", "acquisition"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Quarterly earnings release",
        )
    assert result.category == "financial_results"
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"] == {"type": "json_object"}
    user_prompt = call_kwargs["messages"][1]["content"]
    assert "Symbol: INFY" in user_prompt
    assert "Company: Infosys Ltd" in user_prompt
    assert "Announcement text metadata:" in user_prompt


async def test_openai_analyze_announcement_with_images_and_paging_context():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = _ANALYSIS_JSON
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        page_image = MagicMock(page_number=1, mime_type="image/png", data_base64="aGVsbG8=")
        await provider.analyze_announcement(
            page_images=[page_image],
            categories=["financial_results", "acquisition"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Quarterly earnings release",
            page_range_start=1,
            page_range_end=2,
            total_pages=4,
            provisional_summary="Interim summary",
            response_format_retry=True,
        )
    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    user_content = messages[1]["content"]
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    prompt = user_content[0]["text"]
    assert "Current page range: 1-2" in prompt
    assert "Total pages in announcement: 4" in prompt
    assert "Provisional summary from previous pages: Interim summary" in prompt
    assert "need_more_pages" in prompt
    assert "This is a response-format retry" in prompt


async def test_openai_context_window_error_mapping():
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("maximum context length exceeded")
        )
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        with pytest.raises(LLMContextWindowError):
            await provider.analyze_text_announcement(
                text="Q4 results...",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Quarterly earnings release",
            )


async def test_openai_raises_response_format_error_for_empty_choices():
    mock_response = MagicMock()
    mock_response.choices = []
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        with pytest.raises(LLMResponseFormatError, match="choices"):
            await provider.analyze_text_announcement(
                text="Q4 results...",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Quarterly earnings release",
            )


async def test_anthropic_analyze_text_announcement():
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].type = "text"
    mock_response.content[0].text = _ANALYSIS_JSON
    with patch("llm.anthropic._anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        result = await provider.analyze_text_announcement(
            text="Infosys acquires XYZ...",
            categories=["financial_results", "acquisition"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Acquisition update",
        )
    assert result.summary.startswith("Infosys reported")


async def test_anthropic_analyze_announcement_with_images():
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].type = "text"
    mock_response.content[0].text = _ANALYSIS_JSON
    with patch("llm.anthropic._anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        page_image = MagicMock(page_number=2, mime_type="image/jpeg", data_base64="aGVsbG8=")
        await provider.analyze_announcement(
            page_images=[page_image],
            categories=["financial_results", "acquisition"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Acquisition update",
            page_range_start=2,
            page_range_end=2,
            total_pages=5,
        )
    content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert content[1]["type"] == "image"
    assert content[1]["source"]["media_type"] == "image/jpeg"
    assert "Current page range: 2-2" in content[0]["text"]


async def test_anthropic_raises_response_format_error_for_invalid_json():
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].type = "text"
    mock_response.content[0].text = "not json"
    with patch("llm.anthropic._anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        with pytest.raises(LLMResponseFormatError):
            await provider.analyze_text_announcement(
                text="Bad output",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Bad output",
            )


async def test_anthropic_raises_response_format_error_for_missing_text_block():
    mock_response = MagicMock()
    non_text_block = MagicMock()
    non_text_block.type = "image"
    mock_response.content = [non_text_block]
    with patch("llm.anthropic._anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        with pytest.raises(LLMResponseFormatError, match="text content blocks"):
            await provider.analyze_text_announcement(
                text="Infosys acquires XYZ...",
                categories=["financial_results", "acquisition"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Acquisition update",
            )


async def test_anthropic_raises_response_format_error_for_empty_text_block():
    mock_response = MagicMock()
    empty_text_block = MagicMock()
    empty_text_block.type = "text"
    empty_text_block.text = "  "
    mock_response.content = [empty_text_block]
    with patch("llm.anthropic._anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        with pytest.raises(LLMResponseFormatError, match="empty text"):
            await provider.analyze_text_announcement(
                text="Infosys acquires XYZ...",
                categories=["financial_results", "acquisition"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Acquisition update",
            )


async def test_anthropic_context_window_error_mapping():
    with patch("llm.anthropic._anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("prompt is too long"))
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        with pytest.raises(LLMContextWindowError):
            await provider.analyze_text_announcement(
                text="Long prompt",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Long prompt",
            )


async def test_gemini_analyze_text_announcement():
    mock_response = MagicMock()
    mock_response.text = _ANALYSIS_JSON
    with patch("llm.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client
        provider = GeminiProvider(api_key="test-key")
        result = await provider.analyze_text_announcement(
            text="Launch of new product...",
            categories=["financial_results", "acquisition"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Product launch",
        )
    assert result.confidence == "high"


async def test_gemini_analyze_announcement_with_images():
    mock_response = MagicMock()
    mock_response.text = _ANALYSIS_JSON
    with patch("llm.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_genai.Client.return_value = mock_client
        provider = GeminiProvider(api_key="test-key")
        page_image = MagicMock(page_number=3, mime_type="image/png", data_base64="aGVsbG8=")
        await provider.analyze_announcement(
            page_images=[page_image],
            categories=["financial_results", "acquisition"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Product launch",
            page_range_start=3,
            page_range_end=3,
            total_pages=3,
            provisional_summary="Prior pages covered launch context",
        )
    contents = mock_client.aio.models.generate_content.call_args.kwargs["contents"]
    assert len(contents[0].parts) == 2
    assert "Current page range: 3-3" in contents[0].parts[0].text
    assert "Total pages in announcement: 3" in contents[0].parts[0].text


async def test_gemini_context_window_error_mapping():
    with patch("llm.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("context window exceeded")
        )
        mock_genai.Client.return_value = mock_client
        provider = GeminiProvider(api_key="test-key")
        with pytest.raises(LLMContextWindowError):
            await provider.analyze_text_announcement(
                text="Long prompt",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Long prompt",
            )


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


# ---------------------------------------------------------------------------
# Rate-limit handling — OpenAI
# ---------------------------------------------------------------------------

def _make_openai_rate_limit_error(retry_after: float | None = None) -> Exception:
    from openai import RateLimitError

    response = MagicMock()
    response.headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    response.status_code = 429
    return RateLimitError("rate limit exceeded", response=response, body=None)


async def test_openai_rate_limit_raises_llm_rate_limit_error():
    """When rate-limited with no short retry-after, LLMRateLimitError is raised immediately."""
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=_make_openai_rate_limit_error(retry_after=None)
        )
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.analyze_text_announcement(
                text="Q4 results...",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Quarterly earnings release",
            )
    assert exc_info.value.retry_after is None
    assert mock_client.chat.completions.create.call_count == 1


async def test_openai_rate_limit_retry_after_extracted():
    """retry_after is parsed from the response Retry-After header."""
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=_make_openai_rate_limit_error(retry_after=120.0)
        )
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.analyze_text_announcement(
                text="Q4 results...",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Quarterly earnings release",
            )
    assert exc_info.value.retry_after == 120.0
    assert mock_client.chat.completions.create.call_count == 1


async def test_openai_rate_limit_inline_retry_succeeds(mock_sleep):
    """When retry-after <= 60s, the provider sleeps and retries; success on retry returns normally."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = _ANALYSIS_JSON
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                _make_openai_rate_limit_error(retry_after=5.0),
                mock_response,
            ]
        )
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        result = await provider.analyze_text_announcement(
            text="Q4 results...",
            categories=["financial_results"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Quarterly earnings release",
        )
    assert result.category == "financial_results"
    assert mock_client.chat.completions.create.call_count == 2
    mock_sleep.assert_awaited_once_with(5.0)


async def test_openai_rate_limit_inline_retry_also_rate_limits(mock_sleep):
    """When the retry also rate-limits, LLMRateLimitError is raised with the new retry_after."""
    with patch("llm.openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                _make_openai_rate_limit_error(retry_after=10.0),
                _make_openai_rate_limit_error(retry_after=30.0),
            ]
        )
        mock_cls.return_value = mock_client
        provider = OpenAIProvider(api_key="test-key")
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.analyze_text_announcement(
                text="Q4 results...",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Quarterly earnings release",
            )
    assert exc_info.value.retry_after == 30.0
    assert mock_client.chat.completions.create.call_count == 2
    mock_sleep.assert_awaited_once_with(10.0)


# ---------------------------------------------------------------------------
# Rate-limit handling — Anthropic
# ---------------------------------------------------------------------------

def _make_anthropic_rate_limit_error(retry_after: float | None = None) -> Exception:
    response = MagicMock()
    response.headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    response.status_code = 429
    return MagicMock(
        spec=Exception,
        __class__=__import__("anthropic").RateLimitError,
        response=response,
    )


async def test_anthropic_rate_limit_raises_llm_rate_limit_error():
    with patch("llm.anthropic._anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        import anthropic as _ant

        mock_client.messages.create = AsyncMock(
            side_effect=_ant.RateLimitError(
                "rate limit",
                response=MagicMock(headers={}, status_code=429),
                body=None,
            )
        )
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        with pytest.raises(LLMRateLimitError):
            await provider.analyze_text_announcement(
                text="Launch of new product...",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Product launch",
            )
    assert mock_client.messages.create.call_count == 1


async def test_anthropic_rate_limit_inline_retry_succeeds(mock_sleep):
    import anthropic as _ant

    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].type = "text"
    mock_response.content[0].text = _ANALYSIS_JSON
    with patch("llm.anthropic._anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        rate_limit_exc = _ant.RateLimitError(
            "rate limit",
            response=MagicMock(headers={"retry-after": "15"}, status_code=429),
            body=None,
        )
        mock_client.messages.create = AsyncMock(
            side_effect=[rate_limit_exc, mock_response]
        )
        mock_cls.return_value = mock_client
        provider = AnthropicProvider(api_key="test-key")
        result = await provider.analyze_text_announcement(
            text="Launch of new product...",
            categories=["financial_results"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Product launch",
        )
    assert result.category == "financial_results"
    assert mock_client.messages.create.call_count == 2
    mock_sleep.assert_awaited_once_with(15.0)


# ---------------------------------------------------------------------------
# Rate-limit handling — Gemini
# ---------------------------------------------------------------------------

def _make_gemini_rate_limit_error(retry_after_seconds: float | None = None) -> Exception:
    from google.genai.errors import ClientError

    details = []
    if retry_after_seconds is not None:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": f"{int(retry_after_seconds)}s"})
    response_json = {
        "error": {
            "code": 429,
            "message": "You exceeded your current quota.",
            "status": "RESOURCE_EXHAUSTED",
            "details": details,
        }
    }
    return ClientError(429, response_json, MagicMock())


async def test_gemini_rate_limit_raises_llm_rate_limit_error():
    with patch("llm.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=_make_gemini_rate_limit_error()
        )
        mock_genai.Client.return_value = mock_client
        provider = GeminiProvider(api_key="test-key")
        with pytest.raises(LLMRateLimitError):
            await provider.analyze_text_announcement(
                text="Long prompt",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Long prompt",
            )
    assert mock_client.aio.models.generate_content.call_count == 1


async def test_gemini_rate_limit_retry_after_extracted_from_string():
    """retry_after is parsed from the retryDelay field in the error string."""
    with patch("llm.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=_make_gemini_rate_limit_error(retry_after_seconds=54.0)
        )
        mock_genai.Client.return_value = mock_client
        provider = GeminiProvider(api_key="test-key")
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.analyze_text_announcement(
                text="Long prompt",
                categories=["financial_results"],
                symbol="INFY",
                company="Infosys Ltd",
                announcement_text="Long prompt",
            )
    assert exc_info.value.retry_after == 54.0


async def test_gemini_rate_limit_inline_retry_succeeds(mock_sleep):
    mock_response = MagicMock()
    mock_response.text = _ANALYSIS_JSON
    with patch("llm.gemini.genai") as mock_genai:
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[
                _make_gemini_rate_limit_error(retry_after_seconds=30.0),
                mock_response,
            ]
        )
        mock_genai.Client.return_value = mock_client
        provider = GeminiProvider(api_key="test-key")
        result = await provider.analyze_text_announcement(
            text="Launch of new product...",
            categories=["financial_results"],
            symbol="INFY",
            company="Infosys Ltd",
            announcement_text="Product launch",
        )
    assert result.category == "financial_results"
    assert mock_client.aio.models.generate_content.call_count == 2
    mock_sleep.assert_awaited_once_with(30.0)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_sleep(monkeypatch):
    """Replace asyncio.sleep in all provider modules with a no-op."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr("llm.openai.asyncio.sleep", sleep_mock)
    monkeypatch.setattr("llm.anthropic.asyncio.sleep", sleep_mock)
    monkeypatch.setattr("llm.gemini.asyncio.sleep", sleep_mock)
    return sleep_mock
