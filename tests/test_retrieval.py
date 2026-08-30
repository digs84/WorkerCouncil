"""
Unit tests for app/retrieval.py using small synthetic BetrVG/BDSG-shaped
datasets (no network / no real scrape needed).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.retrieval as retrieval  # noqa: E402


BETRVG_SAMPLE = {
    "law": "Betriebsverfassungsgesetz (BetrVG)",
    "source": "https://www.gesetze-im-internet.de/betrvg/",
    "section_count": 3,
    "sections": [
        {
            "order": 1,
            "section": "§ 1",
            "title_de": "Errichtung von Betriebsräten",
            "text_de": "In Betrieben mit in der Regel mindestens fünf ständigen wahlberechtigten Arbeitnehmern werden Betriebsräte gewählt.",
            "law_abbreviation": "BetrVG",
            "source_url": "https://www.gesetze-im-internet.de/betrvg/",
        },
        {
            "order": 2,
            "section": "§ 87",
            "title_de": "Mitbestimmungsrechte",
            "text_de": "Der Betriebsrat hat mitzubestimmen bei Fragen der Ordnung des Betriebs und des Verhaltens der Arbeitnehmer sowie bei Beginn und Ende der täglichen Arbeitszeit.",
            "law_abbreviation": "BetrVG",
            "source_url": "https://www.gesetze-im-internet.de/betrvg/",
        },
        {
            "order": 3,
            "section": "§ 15",
            "title_de": "Kündigung von Betriebsratsmitgliedern",
            "text_de": "Die Kündigung eines Mitglieds des Betriebsrats ist unzulässig, es sei denn, dass Tatsachen vorliegen, welche den Arbeitgeber zur Kündigung aus wichtigem Grund berechtigen.",
            "law_abbreviation": "BetrVG",
            "source_url": "https://www.gesetze-im-internet.de/betrvg/",
        },
    ],
}

# Deliberately reuses "§ 1" - a real collision with BETRVG_SAMPLE's § 1, to
# exercise the (law_abbreviation, section) disambiguation.
BDSG_SAMPLE = {
    "law": "Bundesdatenschutzgesetz (BDSG)",
    "source": "https://www.gesetze-im-internet.de/bdsg_2018/",
    "section_count": 2,
    "sections": [
        {
            "order": 1,
            "section": "§ 1",
            "title_de": "Anwendungsbereich des Gesetzes",
            "text_de": "Dieses Gesetz gilt für die Verarbeitung personenbezogener Daten durch öffentliche und nicht-öffentliche Stellen.",
            "law_abbreviation": "BDSG",
            "source_url": "https://www.gesetze-im-internet.de/bdsg_2018/",
        },
        {
            "order": 2,
            "section": "§ 26",
            "title_de": "Datenverarbeitung für Zwecke des Beschäftigungsverhältnisses",
            "text_de": "Personenbezogene Daten von Beschäftigten dürfen für Zwecke des Beschäftigungsverhältnisses verarbeitet werden, wenn dies für die Entscheidung über die Begründung eines Beschäftigungsverhältnisses erforderlich ist.",
            "law_abbreviation": "BDSG",
            "source_url": "https://www.gesetze-im-internet.de/bdsg_2018/",
        },
    ],
}

TEST_REGISTRY = [
    {"abbreviation": "BetrVG", "name_de": "Betriebsverfassungsgesetz", "name_en": "Works Constitution Act",
     "source_url": "https://www.gesetze-im-internet.de/betrvg/", "data_file": "betrvg.json"},
    {"abbreviation": "BDSG", "name_de": "Bundesdatenschutzgesetz", "name_en": "Federal Data Protection Act",
     "source_url": "https://www.gesetze-im-internet.de/bdsg_2018/", "data_file": "bdsg.json"},
]


def _write_law_files(tmp_path: Path, monkeypatch, laws: dict[str, dict]) -> None:
    """laws: {"betrvg.json": BETRVG_SAMPLE, ...}. Points retrieval at tmp_path
    and a matching LAW_REGISTRY, and clears the module's lru_caches."""
    for filename, payload in laws.items():
        (tmp_path / filename).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(retrieval, "DATA_DIR", tmp_path)
    monkeypatch.setattr(retrieval, "LAW_REGISTRY", TEST_REGISTRY)
    retrieval.load_law_data.cache_clear()
    retrieval.build_compact_toc.cache_clear()


def test_lexical_search_finds_termination_section(tmp_path, monkeypatch):
    _write_law_files(tmp_path, monkeypatch, {"betrvg.json": BETRVG_SAMPLE})

    results = retrieval.lexical_search("Can a works council member be fired?", top_k=3)
    sections = [r["section"] for r in results]
    assert "§ 15" in sections, f"expected § 15 (termination) in results, got {sections}"


def test_lexical_search_finds_working_hours_section(tmp_path, monkeypatch):
    _write_law_files(tmp_path, monkeypatch, {"betrvg.json": BETRVG_SAMPLE})

    results = retrieval.lexical_search("working hours co-determination", top_k=3)
    sections = [r["section"] for r in results]
    assert "§ 87" in sections, f"expected § 87 (co-determination) in results, got {sections}"


def test_lexical_search_finds_bdsg_section_across_laws(tmp_path, monkeypatch):
    _write_law_files(tmp_path, monkeypatch, {"betrvg.json": BETRVG_SAMPLE, "bdsg.json": BDSG_SAMPLE})

    results = retrieval.lexical_search("personal data processing employment", top_k=3)
    refs = [(r["law_abbreviation"], r["section"]) for r in results]
    assert ("BDSG", "§ 26") in refs, f"expected BDSG § 26 in results, got {refs}"


def test_get_sections_by_number(tmp_path, monkeypatch):
    _write_law_files(tmp_path, monkeypatch, {"betrvg.json": BETRVG_SAMPLE})

    result = retrieval.get_sections_by_number([("BetrVG", "§ 1"), ("BetrVG", "§ 87"), ("BetrVG", "§ 999")])
    assert {r["section"] for r in result} == {"§ 1", "§ 87"}


def test_get_sections_by_number_disambiguates_across_laws(tmp_path, monkeypatch):
    """BetrVG § 1 and BDSG § 1 are different sections that happen to share a
    number - asking for one must not also return the other."""
    _write_law_files(tmp_path, monkeypatch, {"betrvg.json": BETRVG_SAMPLE, "bdsg.json": BDSG_SAMPLE})

    result = retrieval.get_sections_by_number([("BDSG", "§ 1")])
    assert len(result) == 1
    assert result[0]["law_abbreviation"] == "BDSG"
    assert result[0]["title_de"] == "Anwendungsbereich des Gesetzes"


def test_compact_toc_contains_all_sections_grouped_by_law(tmp_path, monkeypatch):
    _write_law_files(tmp_path, monkeypatch, {"betrvg.json": BETRVG_SAMPLE, "bdsg.json": BDSG_SAMPLE})

    toc = retrieval.build_compact_toc()
    for s in BETRVG_SAMPLE["sections"] + BDSG_SAMPLE["sections"]:
        assert s["section"] in toc
    assert "=== BetrVG ===" in toc
    assert "=== BDSG ===" in toc


def test_get_sources_status_reports_missing_law(tmp_path, monkeypatch):
    _write_law_files(tmp_path, monkeypatch, {"betrvg.json": BETRVG_SAMPLE})  # bdsg.json intentionally absent

    statuses = {s["abbreviation"]: s for s in retrieval.get_sources_status()}
    assert statuses["BetrVG"]["loaded"] is True
    assert statuses["BetrVG"]["section_count"] == 3
    assert statuses["BDSG"]["loaded"] is False
