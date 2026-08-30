"""
Unit tests for the free-LLM hop/fallback logic in app/llm_router.py.
No real network calls or API keys are used - HTTP is mocked.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm_router import AllProvidersExhaustedError, chat  # noqa: E402


def _resp(status_code, json_body=None, text=""):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_body or {}
    m.text = text
    return m


@patch.dict("os.environ", {"GROQ_API_KEY": "g", "GEMINI_API_KEY": "gg", "OPENROUTER_API_KEY": "o"})
@patch("app.llm_router.get_hop_order")
@patch("app.llm_router.requests.post")
def test_hops_to_next_provider_on_429(mock_post, mock_hop_order):
    mock_hop_order.return_value = [
        ("groq", "llama-3.3-70b-versatile"),
        ("gemini", "gemini-2.0-flash"),
    ]
    # First hop (Groq) is rate-limited, second hop (Gemini) succeeds.
    mock_post.side_effect = [
        _resp(429, text="rate limited"),
        _resp(200, {"choices": [{"message": {"content": "hello from gemini"}}]}),
    ]

    result = chat([{"role": "user", "content": "hi"}])

    assert result.text == "hello from gemini"
    assert result.provider == "gemini"
    assert mock_post.call_count == 2


@patch.dict("os.environ", {"GROQ_API_KEY": "g"})
@patch("app.llm_router.get_hop_order")
@patch("app.llm_router.requests.post")
def test_skips_hop_with_missing_key(mock_post, mock_hop_order):
    mock_hop_order.return_value = [
        ("gemini", "gemini-2.0-flash"),  # no GEMINI_API_KEY set -> skipped, no HTTP call
        ("groq", "llama-3.1-8b-instant"),
    ]
    mock_post.return_value = _resp(200, {"choices": [{"message": {"content": "ok"}}]})

    result = chat([{"role": "user", "content": "hi"}])

    assert result.provider == "groq"
    assert mock_post.call_count == 1  # gemini hop never hit the network


@patch.dict("os.environ", {"GROQ_API_KEY": "g", "GEMINI_API_KEY": "gg", "OPENROUTER_API_KEY": "o"})
@patch("app.llm_router.get_hop_order")
@patch("app.llm_router.requests.post")
def test_all_hops_exhausted_raises(mock_post, mock_hop_order):
    mock_hop_order.return_value = [
        ("groq", "llama-3.3-70b-versatile"),
        ("gemini", "gemini-2.0-flash"),
        ("openrouter", "nvidia/nemotron-3.5-lightning:free"),
    ]
    mock_post.return_value = _resp(429, text="rate limited")

    try:
        chat([{"role": "user", "content": "hi"}])
        assert False, "expected AllProvidersExhaustedError"
    except AllProvidersExhaustedError as exc:
        assert "3" in str(exc)  # mentions how many hops were tried


@patch.dict("os.environ", {}, clear=True)
@patch("app.llm_router.get_hop_order")
def test_no_hops_configured_raises_immediately(mock_hop_order):
    mock_hop_order.return_value = []
    try:
        chat([{"role": "user", "content": "hi"}])
        assert False, "expected AllProvidersExhaustedError"
    except AllProvidersExhaustedError:
        pass


if __name__ == "__main__":
    test_hops_to_next_provider_on_429()
    test_skips_hop_with_missing_key()
    test_all_hops_exhausted_raises()
    test_no_hops_configured_raises_immediately()
    print("All llm_router tests passed.")
