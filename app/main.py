"""
FastAPI backend for the Worker Council (Betriebsrat) Assistant.

Flow for each user question (German or English - see app/i18n.py):
  1. "Selector" LLM call: given the compact §-number/title table of
     contents of the BetrVG, ask which sections are relevant to the
     question. (Bridges the question's language <-> German law text.)
  2. Look up the full German text of those sections.
  3. "Answerer" LLM call: given the question + the retrieved German
     section text, answer in the SAME language the question was asked
     in, citing § numbers, and propose 2-3 follow-up questions (see
     FOLLOWUP_MARKER) before a matching-language disclaimer is appended.

Both LLM calls go through app.llm_router.chat(), which hops across
Groq -> Gemini -> OpenRouter free models automatically. If every hop is
exhausted, the endpoint falls back to raw keyword search
(app.retrieval.lexical_search) so the app degrades instead of failing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import config, i18n, retrieval
from app.llm_router import AllProvidersExhaustedError, chat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="Worker Council Assistant (Germany)")

SELECTOR_SYSTEM_PROMPT = (
    "You are a legal-text retrieval assistant. You will be given the table "
    "of contents of one or more German laws, grouped under '=== LAW "
    "ABBREVIATION ===' headers, each followed by '§ number: German title' "
    "lines, and a question (in German or English) from a user. Reply with "
    "ONLY a JSON array of up to 6 of the most relevant sections as "
    "{\"law\": \"<abbreviation>\", \"section\": \"<§ number>\"} objects, e.g. "
    "[{\"law\": \"BetrVG\", \"section\": \"§ 87\"}, {\"law\": \"BDSG\", \"section\": \"§ 26\"}]. "
    "Always include the exact law abbreviation from the header the section "
    "came from - section numbers repeat across laws. No prose, no markdown, "
    "just the JSON array."
)

FOLLOWUP_MARKER = "###FOLLOWUP_QUESTIONS_JSON###"

ANSWERER_SYSTEM_PROMPT = (
    "You are a careful assistant helping people in Germany understand "
    "German employment and data-protection law - specifically the "
    "Betriebsverfassungsgesetz (BetrVG, works council law) and the "
    "Bundesdatenschutzgesetz (BDSG, federal data protection act, which "
    "supplements the EU GDPR domestically). You will be given one or more "
    "excerpts of official German legal text, each labeled with its law "
    "abbreviation and § number, and a question, which may be written in "
    "German or English. "
    "IMPORTANT: Answer in the EXACT language requested by the user. "
    "If the question is in German, answer entirely in German; if it is in "
    "English, answer entirely in English. Do not mix languages. "
    "Ground every claim in the excerpts provided and cite both the law "
    "abbreviation and § number inline regardless of language (e.g. 'under "
    "§ 87 BetrVG ...' / 'nach § 26 BDSG ...'). If the excerpts don't fully "
    "answer the question, say so plainly rather than guessing. Do not "
    "state opinions as certain legal conclusions - describe what the law "
    "says and note where a lawyer, works council, or data protection "
    "officer should be consulted for a binding answer. Keep the answer "
    "focused and avoid unnecessary repetition.\n\n"
    "You MUST always end your reply with a follow-up section, even for a "
    "short answer: after your complete answer, on its own line write "
    f"exactly {FOLLOWUP_MARKER} and then, on the next line, a JSON array "
    "of 2-3 short natural follow-up questions the user might reasonably "
    "ask next about this same topic - in the SAME language as your "
    'answer. Example ending: \n' + FOLLOWUP_MARKER + '\n'
    '["Follow-up question one?", "Follow-up question two?"]\n'
    "This follow-up section is required in every reply, with no "
    "exceptions. Do not use this marker anywhere else, and do not mention "
    "it or the follow-up questions within the answer itself."
)


def _split_answer_and_followups(raw_text: str) -> tuple[str, list[str]]:
    """Split the answerer's raw output on FOLLOWUP_MARKER into (answer,
    follow_up_questions). Falls back to (raw_text, []) if the marker is
    missing or the trailing JSON doesn't parse - a malformed follow-up
    block should never break the actual answer."""
    if FOLLOWUP_MARKER not in raw_text:
        return raw_text.strip(), []

    answer_part, _, followup_part = raw_text.partition(FOLLOWUP_MARKER)
    try:
        parsed = json.loads(followup_part.strip())
        if isinstance(parsed, list):
            return answer_part.strip(), [str(q) for q in parsed if str(q).strip()][:3]
    except json.JSONDecodeError:
        pass
    return answer_part.strip(), []


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    answer: str
    cited_sections: list[dict]
    follow_up_questions: list[str] = []
    provider_used: str | None = None
    model_used: str | None = None
    degraded: bool = False
    language: str = "en"
    confidence: str = "medium"
    source_summary: str = ""


def _compute_confidence(section_count: int, degraded: bool) -> str:
    """Confidence level for an answer based on how many sections matched and
    whether it came from degraded fallback mode."""
    if degraded:
        return "low"
    if section_count >= 3:
        return "high"
    if section_count >= 1:
        return "medium"
    return "low"


def _summarize_sources(sections: list[dict]) -> str:
    """Return a compact source summary like '§ 87, § 88 (BetrVG)' for UI."""
    if not sections:
        return ""
    by_law: dict[str, list[str]] = {}
    for s in sections:
        law = str(s.get("law_abbreviation", "")).strip()
        section = str(s.get("section", "")).strip()
        if not law and not section:
            continue
        by_law.setdefault(law, []).append(section)
    if not by_law:
        return ", ".join(str(s.get("section", "")).strip() for s in sections if s.get("section"))
    parts = []
    for law, sections_list in by_law.items():
        unique_sections = list(dict.fromkeys(sections_list))
        parts.append(f"{', '.join(unique_sections)} ({law})" if law else ', '.join(unique_sections))
    return "; ".join(parts)


def select_relevant_sections(question: str) -> list[tuple[str, str]]:
    toc = retrieval.build_compact_toc()
    messages = [
        {"role": "system", "content": SELECTOR_SYSTEM_PROMPT},
        {"role": "user", "content": f"TABLE OF CONTENTS:\n{toc}\n\nQUESTION: {question}"},
    ]
    result = chat(messages, temperature=0.0, max_tokens=700)
    try:
        refs = json.loads(result.text.strip())
        if isinstance(refs, list):
            pairs = [
                (str(r["law"]), str(r["section"]))
                for r in refs
                if isinstance(r, dict) and "law" in r and "section" in r
            ]
            return pairs[:6]
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    logger.warning("Selector call returned unusable output, falling back to lexical search: %r", result.text)
    return []


@app.get("/api/health")
def health():
    hop_order = config.get_hop_order()
    return {
        "status": "ok",
        "law_loaded": retrieval.any_law_loaded(),
        "configured_hops": [f"{p}:{m}" for p, m in hop_order],
    }


@app.get("/api/sources")
def sources():
    """Which laws this app covers, for the frontend's "Holds" pills and
    Sources panel. See app.config.LAW_REGISTRY."""
    return {"laws": retrieval.get_sources_status()}


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")

    language = i18n.detect_language(question)
    disclaimer = i18n.DISCLAIMER[language]

    if not retrieval.any_law_loaded():
        raise HTTPException(
            status_code=503,
            detail="Law data not loaded yet. Run the scripts/fetch_*.py scripts on the server first.",
        )

    # Step 1: pick relevant sections (LLM-assisted, hops across providers)
    try:
        section_refs = select_relevant_sections(question)
        sections = retrieval.get_sections_by_number(section_refs) if section_refs else []
        if not sections:
            sections = retrieval.lexical_search(question, top_k=5)
    except AllProvidersExhaustedError:
        logger.warning("All providers exhausted during section selection; using lexical search only.")
        sections = retrieval.lexical_search(question, top_k=5)

    if not sections:
        return ChatResponse(
            answer=f"{i18n.NO_MATCH_MESSAGE[language]} {disclaimer}",
            cited_sections=[],
            degraded=False,
            language=language,
        )

    excerpts = "\n\n".join(
        f"{s['section']} {s['title_de']}\n{s['text_de']}" for s in sections
    )

    # Step 2: answer, grounded in the retrieved German text, in the
    # question's own language (the system prompt instructs this; the LLM
    # handles DE/EN natively far better than any rule-based translation).
    try:
        messages = [
            {"role": "system", "content": ANSWERER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"TARGET_LANGUAGE: {language}\n"
                    f"EXCERPTS:\n{excerpts}\n\nQUESTION: {question}"
                ),
            },
        ]
        result = chat(messages, temperature=0.2, max_tokens=1500)
        answer_text, follow_ups = _split_answer_and_followups(result.text)
        answer = f"{answer_text}\n\n---\n{disclaimer}"
        answer_confidence = _compute_confidence(len(sections), False)
        return ChatResponse(
            answer=answer,
            cited_sections=sections,
            follow_up_questions=follow_ups,
            provider_used=result.provider,
            model_used=result.model,
            degraded=False,
            language=language,
            confidence=answer_confidence,
            source_summary=_summarize_sources(sections),
        )
    except AllProvidersExhaustedError as exc:
        logger.error("All providers exhausted during answer generation: %s", exc)
        raw = "\n\n".join(
            f"{s['section']} {s['title_de']}:\n{s['text_de']}" for s in sections
        )
        answer_confidence = _compute_confidence(len(sections), True)
        return ChatResponse(
            answer=(
                f"{i18n.ALL_PROVIDERS_EXHAUSTED_PREFIX[language]}\n\n"
                f"{raw}\n\n---\n{disclaimer}"
            ),
            cited_sections=sections,
            degraded=True,
            language=language,
            confidence=answer_confidence,
            source_summary=_summarize_sources(sections),
        )


# Serve the single-page chat frontend + PWA assets.
# manifest.json and sw.js are served from the root path (not /static) on
# purpose: a service worker's default control scope is the directory it's
# served from, and the whole point here is for it to control the whole
# site ("/") so the app shell works offline and is installable.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/manifest.json")
def manifest():
    return FileResponse(str(STATIC_DIR / "manifest.json"), media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(str(STATIC_DIR / "sw.js"), media_type="application/javascript")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(str(STATIC_DIR / "favicon.ico"), media_type="image/x-icon")
