import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.i18n import detect_language  # noqa: E402


def test_detects_german_via_umlaut():
    assert detect_language("Wie wird ein Betriebsrat gewählt?") == "de"


def test_detects_german_via_stopwords_no_umlaut():
    assert detect_language("Kann der Arbeitgeber das ohne Zustimmung machen") == "de"


def test_detects_english():
    assert detect_language("Can the employer change shift start times without asking us?") == "en"


def test_defaults_to_english_on_empty():
    assert detect_language("") == "en"


def test_defaults_to_english_on_ambiguous_short_text():
    assert detect_language("BetrVG") == "en"


def test_keeps_english_when_question_mentions_german_legal_terms():
    assert detect_language("What rights does the Betriebsrat have in Germany?") == "en"


def test_keeps_english_when_asking_about_german_law_in_english():
    assert detect_language("Can the employer require overtime without the works council's approval?") == "en"
