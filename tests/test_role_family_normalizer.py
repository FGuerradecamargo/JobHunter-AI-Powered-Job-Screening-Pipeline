from models.career_evidence import CareerEvidence
from services.career_evidence_aggregator import aggregate_market_evidence
from services.current_market_position_builder import build_current_market_position
from services.role_family_normalizer import normalize_role_family, role_family_key


def _role_record(evidence_id, job_id, role_family):
    return CareerEvidence(
        evidence_id=evidence_id,
        evidence_type="market_signal",
        signal_type="role_family",
        source_ref=f"job:{job_id}",
        statement=role_family,
        role_family=role_family,
        authority="market_evidence",
        metadata={"recommendation": "best_match", "current_fit": 80},
    )


def test_normalizes_case_whitespace_punctuation_and_safe_aliases():
    assert normalize_role_family("  Product   Ops. ") == "Product Operations"
    assert role_family_key("PRODUCT OPS") == "product operations"
    assert normalize_role_family("Customer Ops,") == "Customer Operations"


def test_non_equivalent_role_families_remain_separate():
    assert role_family_key("Product Management") != role_family_key(
        "Product Operations"
    )
    assert role_family_key("Data Analyst") != role_family_key("Data Operations")


def test_aliases_merge_in_market_position_without_inflating_sample():
    position = build_current_market_position(
        candidate_id="candidate-a",
        evidence_records=[
            _role_record("e1", "1", "Product Ops"),
            _role_record("e2", "2", " product operations. "),
        ],
        target_role_families=["PRODUCT OPS"],
    )

    assert position.sample_size == 2
    assert len(position.competitive_role_families) == 1
    assert position.competitive_role_families[0].role_family == (
        "Product Operations"
    )
    assert position.competitive_role_families[0].independent_sources == 2
    assert position.best_match_count == 2


def test_aliases_merge_in_evidence_aggregation():
    signals = aggregate_market_evidence(
        [
            _role_record("e1", "1", "Product Ops"),
            _role_record("e2", "2", "product operations"),
        ]
    )

    assert len(signals) == 1
    assert signals[0].statement == "Product Operations"
    assert signals[0].role_families == ["Product Operations"]

