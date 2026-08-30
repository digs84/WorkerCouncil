"""
Multi-provider free-LLM router.

Tries each (provider, model) hop from config.get_hop_order() in turn.
When a provider is rate-limited, out of quota, unauthorized, or simply
unreachable, it is skipped and the next hop is tried - so the app keeps
answering across Groq -> Gemini -> OpenRouter free models without ever
needing a paid key, as long as at least one hop still has capacity.

All three built-in providers speak the same OpenAI-compatible
/chat/completions REST shape, so this file makes a single kind of HTTP
call and only swaps base_url / api_key / model / headers per hop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from app.config import PROVIDERS, get_hop_order

logger = logging.getLogger("llm_router")

REQUEST_TIMEOUT_SECONDS = 30

# Status codes that mean "this hop is exhausted or unusable right now,
# move on to the next one" rather than "something is wrong with the request
# itself" (which would fail the same way on every hop, so we still move on,
# but it's worth logging distinctly).
RATE_LIMIT_STATUS = {429}
AUTH_STATUS = {401, 403}


class AllProvidersExhaustedError(RuntimeError):
    """Raised when every configured hop failed or is unavailable."""


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    hops_tried: list[str]


def _call_one_hop(provider_name: str, model: str, messages: list[dict],
                   temperature: float, max_tokens: int) -> str:
    spec = PROVIDERS[provider_name]
    import os

    # .strip(): a key pasted into a hosting dashboard with a stray
    # leading/trailing space (easy to do copying out of a ".env"-style
    # file) is otherwise sent as-is in the Authorization header, where
    # every provider just treats it as an invalid key - indistinguishable
    # from a real outage unless you happen to test the same key with and
    # without whitespace.
    api_key = (os.getenv(spec.api_key_env) or "").strip()
    if not api_key:
        raise PermissionError(f"No API key set for {provider_name} ({spec.api_key_env})")

    url = f"{spec.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **spec.extra_headers,
    }
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    resp = requests.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT_SECONDS)

    if resp.status_code in RATE_LIMIT_STATUS:
        raise TimeoutError(f"{provider_name}:{model} rate-limited (HTTP 429)")
    if resp.status_code in AUTH_STATUS:
        raise PermissionError(f"{provider_name}:{model} auth failed (HTTP {resp.status_code}) - check the API key")
    if resp.status_code >= 400:
        raise RuntimeError(f"{provider_name}:{model} HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"{provider_name}:{model} returned an unexpected response shape: {data}") from exc


def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 900) -> ChatResult:
    """Send a chat completion request, hopping across free providers/models
    until one succeeds.

    messages: standard OpenAI-style [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    hop_order = get_hop_order()
    if not hop_order:
        raise AllProvidersExhaustedError(
            "No LLM provider API keys are configured. Copy .env.example to .env "
            "and add at least one of GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY."
        )

    tried: list[str] = []
    last_error: Exception | None = None

    for provider_name, model in hop_order:
        hop_label = f"{provider_name}:{model}"
        tried.append(hop_label)
        try:
            text = _call_one_hop(provider_name, model, messages, temperature, max_tokens)
            logger.info("Answered via %s (tried before this: %s)", hop_label, tried[:-1] or "none")
            return ChatResult(text=text, provider=provider_name, model=model, hops_tried=tried)
        except TimeoutError as exc:
            logger.warning("Hop exhausted (rate limit), hopping to next: %s", exc)
            last_error = exc
            continue
        except PermissionError as exc:
            logger.warning("Hop unusable (auth/config), hopping to next: %s", exc)
            last_error = exc
            continue
        except (requests.RequestException, RuntimeError) as exc:
            logger.warning("Hop failed, hopping to next: %s", exc)
            last_error = exc
            continue

    raise AllProvidersExhaustedError(
        f"All {len(tried)} configured free-LLM hops failed or are rate-limited "
        f"right now: {', '.join(tried)}. Wait a minute and try again, or add "
        f"another provider's free API key to .env. Last error: {last_error}"
    )
