from pathlib import Path


def test_shell_does_not_load_candidate_only_for_product_state():
    source = Path(
        "streamlit_app.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "CandidateRepository"
        not in source
    )

    assert (
        "candidate_id = active_user.candidate_id"
        in source
    )


def test_applications_does_not_duplicate_candidate_lookup():
    source = Path(
        "app.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "CandidateRepository"
        not in source
    )

    assert (
        "CandidateProductStateRepository"
        in source
    )
