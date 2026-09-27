from types import SimpleNamespace

import pytest

from components import job_analysis_view as module


@pytest.fixture
def screen(monkeypatch):
    output = []
    def write(*args, **kwargs):
        output.append(" ".join(str(arg) for arg in args))
    fake = SimpleNamespace(subheader=write, caption=write, info=write, warning=write,
        markdown=write, text=write, html=write, columns=lambda n: [SimpleNamespace(metric=write) for _ in range(n)])
    monkeypatch.setattr(module, "st", fake)
    return output


def item(classification="not_surfaced"):
    return {"id": "job", "recommendation": "best_match", "current_fit": 99,
        "analysis": {"reason": "LEGACY BUCKET REASON", "hiring_case": {
            "authority": "deterministic_hiring_case", "schema_version": "hiring-case-v2",
            "job_id": "job", "classification": classification,
            "hiring_case_strength": "unknown", "opportunity": {"value": "medium", "confidence": "low"},
            "requirements": [{"requirement": "Support", "evidence_state": "evidence_missing"}],
            "candidate_profile_version": 2, "job_profile_version": 3,
        }}}


def test_shared_view_uses_same_case_not_legacy_bucket_or_scores(screen):
    module.render_job_analysis(item())
    rendered = "\n".join(screen)
    assert "More evidence needed" in rendered
    assert "Evidence Missing" in rendered
    assert "Best Match" not in rendered
    assert "99" not in rendered and "LEGACY BUCKET REASON" not in rendered


def test_official_classification_label_is_preserved(screen):
    module.render_job_analysis(item("worth_a_try"))
    assert "Worth a Try" in screen


def test_wrong_job_never_falls_back_to_legacy_recommendation(screen):
    row = item()
    row["analysis"]["hiring_case"]["job_id"] = "another-job"
    module.render_job_analysis(row)
    assert len(screen) == 1
    assert "needs to be refreshed" in screen[0]
