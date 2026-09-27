from pathlib import Path


def test_opportunities_does_not_present_candidate_derived_market_as_market_authority():
    source = Path("pages/1_Opportunities.py").read_text(
        encoding="utf-8"
    )

    assert "services.market_position_service" not in source
    assert "build_market_position(" not in source
    assert 'st.subheader("Market insights")' not in source


def test_official_market_relationship_lives_in_improvements_runtime():
    source = Path("pages/4_Improvements.py").read_text(
        encoding="utf-8"
    )

    assert "load_candidate_market_runtime" in source
    assert "career_intelligence_presenter" not in source
