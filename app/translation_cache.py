"""
Translation cache for German law sections.

Translates German section titles and text to English on-demand using the
configured LLM provider (Groq/Gemini), and caches results locally to avoid
re-translating the same sections.

Cache is stored in data/translation_cache.json for persistence across restarts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.llm_router import chat, AllProvidersExhaustedError

logger = logging.getLogger("translation_cache")

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "translation_cache.json"


def _load_cache() -> dict:
    """Load the translation cache from disk, or return empty dict if not found."""
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not load translation cache: %s", e)
        return {}


def _save_cache(cache: dict) -> None:
    """Save the translation cache to disk."""
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Could not save translation cache: %s", e)


def translate_text(german_text: str, context: str = "law") -> str:
    """
    Translate German text to English, using cache when available.
    
    Args:
        german_text: The German text to translate
        context: Optional context for the translation (e.g., "law", "title")
    
    Returns:
        English translation, or original German text if translation fails
    """
    if not german_text or len(german_text) < 5:
        return german_text
    
    cache = _load_cache()
    
    # Check cache first
    cache_key = german_text[:100]  # Use first 100 chars as key
    if cache_key in cache:
        logger.debug("Cache hit for translation")
        return cache[cache_key]
    
    # Translate using LLM
    try:
        prompt = f"Translate the following German text to clear, plain English:\n\n{german_text}"
        messages = [
            {"role": "system", "content": "You are a translator of German legal text to English. Translate accurately and concisely. Reply with ONLY the English translation, no additional text."},
            {"role": "user", "content": prompt}
        ]
        
        result = chat(messages, temperature=0.0, max_tokens=min(len(german_text) // 3 + 100, 2000))
        translation = result.text.strip()
        
        if translation and translation != german_text:
            # Cache the translation
            cache[cache_key] = translation
            _save_cache(cache)
            logger.debug("Translated and cached: %s...", german_text[:50])
            return translation
    except AllProvidersExhaustedError:
        logger.warning("All LLM providers exhausted during translation, using German")
    except Exception as e:
        logger.error("Translation error: %s", e)
    
    # Fallback: return original German
    return german_text


def get_translated_sections(sections: list[dict]) -> list[dict]:
    """
    Translate section titles and text to English, caching results.
    
    Returns the sections with 'title_en' and 'text_en' keys added.
    """
    cache = _load_cache()
    
    for section in sections:
        section_key = section["section"]
        
        # Translate title
        title_cache_key = f"{section_key}:title:{section['title_de'][:50]}"
        if title_cache_key in cache:
            section["title_en"] = cache[title_cache_key]
        else:
            section["title_en"] = translate_text(section["title_de"], "title")
            cache[title_cache_key] = section["title_en"]
        
        # Translate text (do this less frequently to save API calls)
        # You could skip this if you want to keep API usage low
        # and only translate on-demand when the section is shown to the user
    
    _save_cache(cache)
    return sections
