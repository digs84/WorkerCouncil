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
    extra_body: dict = field(default_factory=dict)
    # Per-provider override for app.llm_router.REQUEST_TIMEOUT_SECONDS.
    # None means "use the module default".
    timeout_seconds: int | None = None


PROVIDERS: dict[str, ProviderSpec] = {
    "ollama": ProviderSpec(
        name="ollama",
        # Ollama's OpenAI-compatible endpoint - only reachable when Ollama
        # is installed and running on THIS machine (or wherever
        # OLLAMA_BASE_URL points). It doesn't check the Authorization
        # header at all, so any non-empty OLLAMA_API_KEY value just serves
        # as this app's own "hop is enabled" switch (see .env.example) -
        # there's no real key to sign up for. Local-only: this hop is
        # useless to the deployed Netlify site, which can't reach your
        # machine's localhost - see app/config.py module docstring.
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key_env="OLLAMA_API_KEY",
        # These are just reasonable guesses - replace with whatever model(s)
        # you've actually pulled (`ollama pull <name>`), or override via
        # LLM_HOP_ORDER. A wrong name here just 404s and hops on to Groq/etc,
        # same as any other misconfigured hop.
        default_models=[
            "llama3.1",
            "qwen2.5",
        ],
        # CPU-only local inference measured live at ~14s for a 2-token
        # reply once warm, and 30-70s+ including a cold model load - far
        # past the 30s default that's sized for cloud APIs. A real answer
        # (~150-250 tokens, longer prompt) needs much more room than that.
        timeout_seconds=120,
    ),
    "groq": ProviderSpec(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        default_models=[
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
        ],
        # gpt-oss models spend a variable, sometimes huge, chunk of
        # max_tokens on hidden reasoning before writing any visible answer -
        # confirmed live: a real request burned 355 of 559 completion tokens
        # on reasoning, and with a longer real prompt (multiple retrieved §
        # excerpts) that reasoning alone consumed the entire budget, cutting
        # the response off with an EMPTY visible answer. "low" cut reasoning
        # tokens 355->44 (8x) with no loss in answer quality or accuracy.
        extra_body={"reasoning_effort": "low"},
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
        # Confirmed live: without this, a free reasoning model on OpenRouter
        # sometimes puts its ENTIRE chain-of-thought straight into the
        # visible "content" field instead of the separate "reasoning" field
        # (not consistently - the same model can behave correctly on a
        # simple prompt and leak on a longer, real one), producing a
        # nonsense wall-of-thinking-steps answer instead of an actual reply.
        # "exclude" tells OpenRouter to strip reasoning server-side
        # regardless of which field the underlying model tries to put it
        # in, which also cut total tokens ~40% in testing (628->373).
        extra_body={"reasoning": {"exclude": True}},
    ),
}

# Gemini's free tier is only 20 requests/day per model (confirmed via its
# own 429 response), so trying it before OpenRouter (20/min, 50/day) just
# wastes a hop attempt on something almost always exhausted. Groq first
# (best free-tier limits), OpenRouter second, Gemini third.
#
# Ollama last, not first: it's genuinely unlimited, but measured live on
# CPU-only hardware at ~14s just for a trivial 2-token reply (a real answer
# took 70s+ end to end and STILL fell through to Groq anyway) - trying it
# before the cloud providers would add that latency to every single
# question even though Groq/etc. almost always just work. As a last resort
# after every rate-limited/cloud hop is exhausted, that latency is a fair
# trade for a free answer instead of none. If your hardware is fast (GPU),
# moving "ollama" first is reasonable - see timeout_seconds on its
# ProviderSpec too.
#
# Cerebras was tried here too but dropped: its "free tier" returns HTTP 402
# Payment Required on every model for a fresh account with no card on file,
# so it wasn't actually usable without paying - see git history if this is
# ever worth revisiting once/if that changes.
PROVIDER_PRIORITY = ["groq", "openrouter", "gemini", "ollama"]


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
