"""
Central configuration: loads .env, and defines the "hop order" of free LLM
providers/models the router will try, one after another, until one answers.

All three built-in providers expose an OpenAI-compatible /chat/completions
endpoint, so app/llm_router.py only needs one HTTP call shape - it just
swaps base_url / api_key / model per hop.

  Groq        https://api.groq.com/openai/v1
  Gemini      https://generativelanguage.googleapis.com/v1beta/openai
  OpenRouter  https://openrouter.ai/api/v1   (models ending in ":free")

Model IDs and free-tier limits on all three change over time. If a model
name below starts returning "model not found" errors, check the provider's
current model list (links in README.md) and either edit DEFAULT hop below
or set LLM_HOP_ORDER in your .env - no other code needs to change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    base_url: str
    api_key_env: str
    default_models: list[str]
    extra_headers: dict[str, str] = field(default_factory=dict)


PROVIDERS: dict[str, ProviderSpec] = {
    "groq": ProviderSpec(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        default_models=[
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
        ],
    ),
    "gemini": ProviderSpec(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env="GEMINI_API_KEY",
        default_models=[
            "gemini-3.6-flash",
            "gemini-3.5-flash",
        ],
    ),
    "openrouter": ProviderSpec(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        default_models=[
            "nvidia/nemotron-3.5-lightning:free",
            "minimax/minimax-m3:free",
            "z-ai/glm-5-2:free",
            "liquid/lfm-2.5-2.6b:free",
        ],
        extra_headers={
            "HTTP-Referer": "https://localhost/worker-council-app",
            "X-Title": "Worker Council Assistant (Germany)",
        },
    ),
}

# Gemini's free tier is only 20 requests/day per model (confirmed via its
# own 429 response), so trying it before OpenRouter (20/min, 50/day) just
# wastes a hop attempt on something almost always exhausted. Groq first
# (best free-tier limits), OpenRouter second, Gemini last as a rarely-
# useful final fallback.
PROVIDER_PRIORITY = ["groq", "openrouter", "gemini"]


# ---------------------------------------------------------------------------
# Law registry: which laws this app covers - see README "Extending to other
# laws". BetrVG (works council law) and BDSG (data protection law) are
# configured today. To add another law (e.g. AGG, ArbSchG, MuSchG):
#   1. Copy scripts/fetch_bdsg.py, change LAW_SLUG and the output filename.
#   2. Add an entry here with a *distinct* "abbreviation" and "data_file"
#      (the abbreviation must exactly match what the fetch script stamps
#      into each section's "law_abbreviation" field, since retrieval.py
#      uses (law_abbreviation, section) pairs to disambiguate sections
#      that share the same § number across different laws).
#   3. app/retrieval.py loads every registry entry's data_file and merges
#      their sections, so the selector/answerer and the frontend's "Holds"
#      row pick up the new law automatically - no other code changes needed.
# ---------------------------------------------------------------------------
LAW_REGISTRY = [
    {
        "slug": "betrvg",
        "abbreviation": "BetrVG",
        "name_de": "Betriebsverfassungsgesetz",
        "name_en": "Works Constitution Act",
        "source_url": "https://www.gesetze-im-internet.de/betrvg/",
        "data_file": "betrvg.json",
    },
    {
        "slug": "bdsg_2018",
        "abbreviation": "BDSG",
        "name_de": "Bundesdatenschutzgesetz",
        "name_en": "Federal Data Protection Act",
        "source_url": "https://www.gesetze-im-internet.de/bdsg_2018/",
        "data_file": "bdsg.json",
    },
]


def _default_hop_order() -> list[tuple[str, str]]:
    hops: list[tuple[str, str]] = []
    for provider_name in PROVIDER_PRIORITY:
        spec = PROVIDERS[provider_name]
        if not (os.getenv(spec.api_key_env) or "").strip():
            continue  # skip providers the user hasn't signed up for
        for model in spec.default_models:
            hops.append((provider_name, model))
    return hops


def get_hop_order() -> list[tuple[str, str]]:
    """Returns an ordered list of (provider_name, model_name) to try.

    Reads LLM_HOP_ORDER from the environment if set (comma-separated
    "provider:model" pairs), otherwise builds the default order from
    whichever provider API keys are present in .env.
    """
    override = os.getenv("LLM_HOP_ORDER", "").strip()
    if not override:
        return _default_hop_order()

    hops = []
    for entry in override.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            continue
        provider_name, model = entry.split(":", 1)
        provider_name = provider_name.strip()
        model = model.strip()
        if provider_name in PROVIDERS:
            hops.append((provider_name, model))
    return hops


HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
