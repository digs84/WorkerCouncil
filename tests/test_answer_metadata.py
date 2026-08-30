from app.main import _compute_confidence, _summarize_sources


def test_compute_confidence_for_direct_source_match():
    assert _compute_confidence(3, False) == "high"
    assert _compute_confidence(1, False) == "medium"
    assert _compute_confidence(0, False) == "low"


def test_compute_confidence_for_degraded_mode():
    assert _compute_confidence(2, True) == "low"


def test_summarize_sources():
    assert _summarize_sources([
        {"law_abbreviation": "BetrVG", "section": "§ 87"},
        {"law_abbreviation": "BetrVG", "section": "§ 88"},
    ]) == "§ 87, § 88 (BetrVG)"
