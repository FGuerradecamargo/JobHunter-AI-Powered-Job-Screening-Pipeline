from pathlib import Path


def test_readiness_uses_single_snapshot_lookup():
    source = Path(
        "services/profile_readiness_service.py"
    ).read_text(
        encoding="utf-8"
    )

    check_source = source[
        source.index("    def check("):
        source.index("    def backfill_missing(")
    ]

    assert (
        "current_candidate("
        in check_source
    )

    assert (
        "candidate_for_signature("
        not in check_source
    )

    assert (
        "candidate_for_readiness("
        not in check_source
    )


def test_onboarding_step_four_reuses_loaded_records():
    source = Path(
        "components/onboarding.py"
    ).read_text(
        encoding="utf-8"
    )

    step_four = source[
        source.index(
            "            elif step == 4:"
        ):
    ]

    before_header = step_four[
        :step_four.index(
            '                st.subheader("BUILD YOUR PROFILE")'
        )
    ]

    assert (
        "get_onboarding("
        not in before_header
    )

    assert (
        "list_work_experiences("
        not in before_header
    )
