from services.job_family_affinity import (
    score_job_family_affinity,
)


def test_target_technical_support_matches_catalog():
    result = score_job_family_affinity(
        target_families=[
            "Technical Support Engineering",
        ],
        evidence=[
            "IT & Technical Support",
            "Technical Support",
            "technical support engineer",
        ],
    )

    assert result.tier == "target"
    assert result.score >= 300


def test_target_fraud_risk_matches_fraud_analysis():
    result = score_job_family_affinity(
        target_families=[
            "Fraud & Risk Analytics",
        ],
        evidence=[
            "Fraud & Risk",
            "Fraud Analysis",
        ],
    )

    assert result.tier == "target"
    assert result.score >= 300


def test_bridge_used_when_target_does_not_match():
    result = score_job_family_affinity(
        target_families=[
            "Technical Support Engineering",
        ],
        bridge_families=[
            "Support Analytics",
        ],
        evidence=[
            "Data & Analytics",
            "Data Analysis",
        ],
    )

    assert result.tier == "bridge"
    assert result.score >= 200


def test_competitive_family_is_lower_priority():
    result = score_job_family_affinity(
        target_families=[
            "Technical Support Engineering",
        ],
        bridge_families=[
            "Fraud & Risk Analytics",
        ],
        competitive_families=[
            "Support Operations",
        ],
        evidence=[
            "Customer Support",
            "Customer Operations",
        ],
    )

    assert result.tier == "competitive"
    assert result.score >= 100


def test_unrelated_job_remains_fallback():
    result = score_job_family_affinity(
        target_families=[
            "Technical Support Engineering",
        ],
        bridge_families=[
            "Fraud & Risk Analytics",
        ],
        competitive_families=[
            "Customer Operations",
        ],
        evidence=[
            "HR / Recruitment",
            "Talent Acquisition",
        ],
    )

    assert result.tier == "fallback"
    assert result.score == 0


def test_generic_operations_does_not_fake_technical_operations_match():
    result = score_job_family_affinity(
        target_families=[
            "Technical Operations",
        ],
        evidence=[
            "Operations",
        ],
    )

    assert result.tier == "fallback"


def test_generic_analytics_does_not_fake_fraud_risk_match():
    result = score_job_family_affinity(
        target_families=[
            "Fraud & Risk Analytics",
        ],
        evidence=[
            "Data Analysis",
        ],
    )

    assert result.tier == "fallback"


def test_target_wins_when_target_and_bridge_both_match():
    result = score_job_family_affinity(
        target_families=[
            "Technical Support Engineering",
        ],
        bridge_families=[
            "Technical Support",
        ],
        evidence=[
            "Technical Support",
        ],
    )

    assert result.tier == "target"


def test_normalization_is_case_and_whitespace_insensitive():
    result = score_job_family_affinity(
        target_families=[
            "  TECHNICAL   SUPPORT ENGINEERING ",
        ],
        evidence=[
            "technical support",
        ],
    )

    assert result.tier == "target"
