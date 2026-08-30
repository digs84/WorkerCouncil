"""
Retrieval layer over the scraped law sections in data/*.json - one file per
app.config.LAW_REGISTRY entry (BetrVG, BDSG, ...).

The source laws are in German; users ask in English. Rather than pre-
translating every section up front (slow, burns free-tier quota, and bakes
in one-shot translation errors), retrieval works in two tiers:

1. Primary path (used whenever any LLM hop is available): the LLM itself
   is shown a compact table of contents (per law: § number + German title)
   and asked which sections are relevant to the question. This lets a
   multilingual model do the German<->English matching, which is far more
   reliable than English keyword search over German text. See
   app/main.py select_relevant_sections().

2. Degraded fallback path (used only if every free LLM hop is exhausted):
   a small bilingual glossary of common German labour-law/data-protection
   terms + plain word-overlap scoring, so the app can still surface raw
   (untranslated) law text instead of failing outright.

Section numbers ("§ 1", "§ 5", ...) are NOT unique across laws - BetrVG and
BDSG each have their own "§ 1". Every section carries a "law_abbreviation"
field, and callers that look sections up by number (get_sections_by_number)
must pass (law_abbreviation, section) pairs, not bare section strings.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.config import LAW_REGISTRY

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Small, hand-curated EN -> DE glossary for the degraded (no-LLM) fallback
# search only. Not exhaustive - just enough to catch the most common things
# a worker or works council member would search for.
GLOSSARY: dict[str, list[str]] = {
    "works council": ["betriebsrat"],
    "worker council": ["betriebsrat"],
    "election": ["wahl", "wahlen"],
    "termination": ["kündigung"],
    "dismissal": ["kündigung", "entlassung"],
    "firing": ["kündigung"],
    "co-determination": ["mitbestimmung"],
    "codetermination": ["mitbestimmung"],
    "meeting": ["versammlung", "sitzung"],
    "works meeting": ["betriebsversammlung"],
    "confidentiality": ["schweigepflicht", "geheimhaltung"],
    "protection": ["schutz"],
    "working hours": ["arbeitszeit"],
    "overtime": ["mehrarbeit", "überstunden"],
    "training": ["schulung", "bildung", "fortbildung"],
    "data protection": ["datenschutz"],
    "discrimination": ["diskriminierung", "benachteiligung"],
    "transfer": ["versetzung"],
    "grievance": ["beschwerde"],
    "complaint": ["beschwerde"],
    "costs": ["kosten"],
    "office space": ["räume", "sachmittel"],
    "release from duties": ["freistellung"],
    "economic committee": ["wirtschaftsausschuss"],
    "youth representative": ["jugend", "auszubildendenvertretung"],
    "works agreement": ["betriebsvereinbarung"],
    "collective agreement": ["tarifvertrag"],
    "employer": ["arbeitgeber"],
    "employee": ["arbeitnehmer"],
    "personnel": ["personal"],
    "hiring": ["einstellung"],
    "job posting": ["ausschreibung"],
    # Data protection (BDSG) terms.
    "personal data": ["personenbezogene daten"],
    "data subject": ["betroffene", "betroffenen"],
    "consent": ["einwilligung"],
    "processing": ["verarbeitung"],
    "data protection officer": ["datenschutzbeauftragte", "datenschutzbeauftragter"],
    "data breach": ["datenschutzverletzung", "verletzung des schutzes"],
    "right to access": ["auskunft"],
    "right to erasure": ["löschung"],
    "deletion": ["löschung"],
    "delete": ["löschung"],
    "erase": ["löschung"],
    "erasure": ["löschung"],
    "right to information": ["auskunftsrecht", "auskunft"],
    "supervisory authority": ["aufsichtsbehörde"],
    "video surveillance": ["videoüberwachung"],
    "employee data": ["beschäftigtendaten"],
    "special categories of data": ["besondere kategorien"],
    "profiling": ["profiling"],
    "fine": ["bußgeld", "geldbuße"],
    "damages": ["schadensersatz"],
    "third country transfer": ["drittstaat", "übermittlung"],
}


@lru_cache(maxsize=1)
def load_law_data() -> dict:
    """Merge sections from every law in app.config.LAW_REGISTRY whose data
    file exists on disk. A law whose fetch script hasn't been run yet (or
    failed at startup) is silently skipped rather than failing the whole
    app - see get_sources_status() for surfacing that state to the user."""
    all_sections: list[dict] = []
    for entry in LAW_REGISTRY:
        law_path = DATA_DIR / entry["data_file"]
        if not law_path.exists():
            continue
        data = json.loads(law_path.read_text(encoding="utf-8"))
        all_sections.extend(data.get("sections", []))

    if not all_sections:
        configured = ", ".join(entry["data_file"] for entry in LAW_REGISTRY)
        raise FileNotFoundError(
            f"No law data found in {DATA_DIR} (looked for: {configured}). "
            f"Run the matching scripts/fetch_*.py for at least one law first."
        )
    return {"sections": all_sections}


def any_law_loaded() -> bool:
    """True if at least one law in LAW_REGISTRY has its data file on disk."""
    return any((DATA_DIR / entry["data_file"]).exists() for entry in LAW_REGISTRY)


def get_sources_status() -> list[dict]:
    """Status of every law in app.config.LAW_REGISTRY, for the /api/sources
    endpoint and the frontend's "Holds" pills."""
    statuses = []
    for entry in LAW_REGISTRY:
        law_path = DATA_DIR / entry["data_file"]
        loaded = law_path.exists()
        section_count = None
        if loaded:
            try:
                data = json.loads(law_path.read_text(encoding="utf-8"))
                section_count = len(data.get("sections", []))
            except (json.JSONDecodeError, OSError):
                loaded = False
        statuses.append(
            {
                "abbreviation": entry["abbreviation"],
                "name_de": entry["name_de"],
                "name_en": entry["name_en"],
                "source_url": entry["source_url"],
                "loaded": loaded,
                "section_count": section_count,
            }
        )
    return statuses


@lru_cache(maxsize=1)
def build_compact_toc() -> str:
    """§ number + German title, grouped by law under a header line - small
    enough to hand an LLM whole so it can pick relevant sections itself.
    The law header lets the model tell apart e.g. BetrVG's § 1 from BDSG's
    § 1 when it names sections back in select_relevant_sections()."""
    data = load_law_data()
    by_law: dict[str, list[str]] = {}
    for s in data["sections"]:
        title = s["title_de"] or "(no title)"
        by_law.setdefault(s["law_abbreviation"], []).append(f"{s['section']}: {title}")

    blocks = [
        f"=== {law} ===\n" + "\n".join(lines)
        for law, lines in by_law.items()
    ]
    return "\n\n".join(blocks)


def get_sections_by_number(refs: list[tuple[str, str]]) -> list[dict]:
    """refs: list of (law_abbreviation, section) pairs, e.g. [("BetrVG", "§ 87")].
    Section numbers repeat across laws, so both parts are required to
    identify a section unambiguously."""
    data = load_law_data()
    wanted = {(law.strip(), section.strip()) for law, section in refs}
    return [
        s for s in data["sections"]
        if (s["law_abbreviation"].strip(), s["section"].strip()) in wanted
    ]


def _expand_query_terms(query: str) -> set[str]:
    from app.i18n import detect_language  # local import: avoids a cycle at module load time

    q = query.lower()
    terms: set[str] = set()
    # Only add the query's own raw words when it's German: they're then
    # genuine German legal terms worth substring-matching directly. For an
    # English query, a raw word like "and" or "does" would otherwise
    # spuriously substring-match unrelated German words (e.g. "and" inside
    # "andere"/"anderen"/"Gegenstand"), swamping the real signal from the
    # glossary below with noise.
    if detect_language(query) == "de":
        terms.update(re.findall(r"[a-zäöüß]+", q))

    def _common_prefix_len(a: str, b: str) -> int:
        i = 0
        while i < len(a) and i < len(b) and a[i] == b[i]:
            i += 1
        return i

    query_words = re.findall(r"[a-z]+", q)
    for phrase, de_terms in GLOSSARY.items():
        if " " in phrase:
            # Multi-word phrases ("personal data", "works council") are
            # compound concepts, not easily stemmed - match as a literal
            # substring.
            matched = phrase in q
        else:
            # Single-word keys match by shared prefix, not exact word or
            # full startswith, so "dismissed"/"dismissal"/"dismissing" all
            # hit the same glossary entry even though none is a prefix of
            # another (they share only "dismiss", 7 of 9-10 letters).
            # Without this, a query using an unlisted inflection (e.g.
            # asking "dismissed" when only "dismissal" was in the
            # glossary) loses its only discriminating term and falls back
            # to whatever generic word (like "works council") happens to
            # be common to nearly every section, making the ranking
            # essentially noise.
            matched = any(
                len(w) >= 4 and len(phrase) >= 4 and _common_prefix_len(w, phrase) >= 4
                for w in query_words
            )
        if matched:
            terms.update(de_terms)
    return terms


# Caps how many times any single term can count towards a section's score.
# Without this, a broad glossary term like "employer" -> "arbeitgeber"
# (ubiquitous in legal text) can rack up a huge raw count and drown out a
# rarer, far more diagnostic term like "löschung" that only appears a
# handful of times but pinpoints the actually relevant section.
MAX_TERM_CONTRIBUTION = 4


def lexical_search(query: str, top_k: int = 5) -> list[dict]:
    """Degraded-mode search used only when no LLM hop is available at all.
    Plain overlap scoring between (glossary-expanded) query terms and each
    section's German title + text. Good enough to point a user at roughly
    the right §§ even with zero AI calls."""
    data = load_law_data()
    terms = _expand_query_terms(query)
    if not terms:
        return []

    scored = []
    for s in data["sections"]:
        haystack = f"{s['title_de']} {s['text_de']}".lower()
        score = sum(min(haystack.count(t), MAX_TERM_CONTRIBUTION) for t in terms if len(t) > 2)
        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [s for _, s in scored[:top_k]]
