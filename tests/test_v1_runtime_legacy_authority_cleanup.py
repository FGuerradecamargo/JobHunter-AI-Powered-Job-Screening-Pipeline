from pathlib import Path


def test_candidate_analysis_has_no_dead_legacy_recommendation_runtime():
    source = Path(
        "services/candidate_job_analysis_service.py"
    ).read_text(encoding="utf-8")

    assert "JobMatcher" not in source
    assert "CandidateFitAnalyzer" not in source
    assert "RecommendationEngine" not in source
    # Kept only as a monkeypatch-compatible test seam.
    # Runtime authority must never call it.
    assert "candidate_to_profile(" not in source
    assert "classify_job_bucket" not in source

    # Current official runtime boundaries remain.
    assert "AIRecommendationService" in source
    assert "analyze_hiring_cases_batch" in source
    assert "JobProfileManager" in source


def test_stale_head_backup_is_not_part_of_repository():
    assert not Path(
        "candidate_job_analysis_service_HEAD_backup.py"
    ).exists()
