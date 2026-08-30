"""
Lightweight bilingual (German / English) support.

The actual answer generation is handled by the LLM itself (it's told, in
the system prompt, to answer in whichever language the question was
asked in - modern free-tier models handle DE/EN fine on their own).

This module only handles the small pieces that happen in plain Python
*before* or *around* the LLM call, where we need to know the question's
language ourselves: which disclaimer text to append, and what to say in
the handful of fixed fallback/error messages that don't go through the
LLM at all (e.g. "all providers exhausted").

Detection is a simple heuristic (German-specific characters + a stopword
score), not a full language-ID model - good enough to pick between two
known languages for a handful of fixed strings. It is NOT used to steer
the LLM's own answer language; that's the system prompt's job.
"""

from __future__ import annotations

import re

GERMAN_CHARS = set("äöüßÄÖÜ")

# Common question starters and function words. These are weighted more
# heavily than isolated legal nouns such as "Betriebsrat" so an English
# sentence that mentions a German legal term is still classified as EN.
GERMAN_QUESTION_PREFIXES = (
    "wie ", "was ", "warum ", "wann ", "wo ", "wer ", "welche ", "welches ",
    "kann ", "muss ", "darf ", "ist ", "sind ", "wird ", "werden ",
    "dürfen ", "können ", "müssen ", "ohne ", "wenn ", "nicht ",
)
ENGLISH_QUESTION_PREFIXES = (
    "what ", "why ", "when ", "where ", "who ", "which ", "how ",
    "can ", "must ", "may ", "is ", "are ", "will ", "does ", "do ",
    "should ", "could ", "would ", "without ", "if ", "not ",
)

# Common short function words, cheap and reliable signal for DE vs EN.
GERMAN_STOPWORDS = {
    "der", "die", "das", "und", "ist", "wie", "kann", "muss", "darf",
    "wird", "werden", "eine", "einen", "einem", "einer", "nicht", "auf",
    "mit", "für", "von", "bei", "ohne", "wenn", "was", "wer", "wo",
    "warum", "wieso", "arbeitgeber", "arbeitnehmer", "betriebsrat",
    "kündigung", "gehalt", "urlaub", "dürfen", "können", "müssen",
}
ENGLISH_STOPWORDS = {
    "the", "is", "can", "does", "do", "must", "may", "will", "a", "an",
    "not", "on", "with", "for", "from", "at", "without", "if", "what",
    "who", "where", "why", "employer", "employee", "works", "council",
    "termination", "salary", "vacation", "how", "which", "when",
}


def detect_language(text: str) -> str:
    """Returns 'de' or 'en'. Defaults to 'en' on a tie or empty input."""
    if not text or not text.strip():
        return "en"

    lowered = text.lower()
    has_german_chars = any(ch in GERMAN_CHARS for ch in text)
    has_english_prefix = any(lowered.startswith(prefix) for prefix in ENGLISH_QUESTION_PREFIXES)
    has_german_prefix = any(lowered.startswith(prefix) for prefix in GERMAN_QUESTION_PREFIXES)

    if has_english_prefix and not has_german_prefix:
        return "en"
    if has_german_prefix and not has_english_prefix:
        return "de"
    if has_german_chars and not has_english_prefix:
        return "de"

    words = set(re.findall(r"[a-zA-Z]+", lowered))
    de_score = len(words & GERMAN_STOPWORDS)
    en_score = len(words & ENGLISH_STOPWORDS)

    if de_score == en_score:
        return "en"
    return "de" if de_score > en_score else "en"


DISCLAIMER = {
    "en": (
        "This is general information based on the official text of the "
        "German laws this app covers (see the Sources panel), "
        "machine-translated and explained for English speakers. It is NOT "
        "legal advice. For a decision that affects you, confirm the answer "
        "with your works council (Betriebsrat), your data protection "
        "officer, your union, or a lawyer specializing in German labour or "
        "data protection law (Arbeitsrecht / Datenschutzrecht)."
    ),
    "de": (
        "Dies sind allgemeine Informationen auf Basis des offiziellen Textes "
        "der von dieser App abgedeckten Gesetze (siehe das Quellen-Panel). "
        "Es handelt sich NICHT um eine Rechtsberatung. Bestätigen Sie "
        "wichtige Entscheidungen bitte mit Ihrem Betriebsrat, Ihrem "
        "Datenschutzbeauftragten, Ihrer Gewerkschaft oder einem Fachanwalt "
        "für Arbeits- oder Datenschutzrecht."
    ),
}

NO_MATCH_MESSAGE = {
    "en": (
        "I couldn't find a relevant section in the laws this app covers for "
        "that question. Try rephrasing, or mention a specific topic (e.g. "
        "'works council elections', 'co-determination', 'termination', "
        "'data protection officer', 'right to erasure')."
    ),
    "de": (
        "Ich konnte dazu keinen passenden Abschnitt in den von dieser App "
        "abgedeckten Gesetzen finden. Versuchen Sie es mit anderen Worten "
        "oder nennen Sie ein konkretes Thema (z. B. 'Betriebsratswahl', "
        "'Mitbestimmung', 'Kündigung', 'Datenschutzbeauftragter', "
        "'Löschungsanspruch')."
    ),
}

ALL_PROVIDERS_EXHAUSTED_PREFIX = {
    "en": (
        "All configured free AI providers are rate-limited or unavailable "
        "right now, so here is the raw (untranslated) text of the German "
        "law sections that best match your question instead:"
    ),
    "de": (
        "Alle konfigurierten kostenlosen KI-Anbieter sind gerade ausgelastet "
        "oder nicht erreichbar. Hier ist stattdessen der unübersetzte Text der "
        "passendsten Gesetzesabschnitte:"
    ),
}
