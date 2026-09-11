from dataclasses import replace

import pytest

from models.application_context import ApplicationContext
from models.application_contract import ApplicationEvidenceRef
from models.tailored_cv_contract import (
    DraftTailoredCV,
    DraftTailoredCVExperience,
    TailoredCVStatement,
)
from services.tailored_cv_generation_request_builder import (
    build_tailored_cv_generation_request,
)
from services.tailored_cv_truth_guard import validate_tailored_cv_draft


def _evidence(ref, source_type, source_id, authority, statement):
    return ApplicationEvidenceRef(
        evidence_ref=ref,
        source_type=source_type,
        source_id=source_id,
        authority=authority,
        statement=statement,
    )


def _context():
    direct = _evidence(
        "e-direct",
        "professional_experience",
        "experience-1",
        "professional_fact",
        "Managed support escalations",
    )
    proven = _evidence(
        "e-proven",
        "proven_capability",
        "candidate:proven",
        "professional_fact",
        "Process improvement",
    )
    transferable = _evidence(
        "e-transferable",
        "transferable_capability",
        "candidate:transferable",
        "transferable_evidence",
        "Stakeholder communication",
    )
    supporting = _evidence(
        "e-skill",
        "skill",
        "candidate:skills",
        "candidate_profile_fact",
        "SQL",
    )
    developing = _evidence(
        "e-developing",
        "developing_capability",
        "candidate:developing",
        "developing_evidence",
        "Kubernetes fundamentals",
    )
    irrelevant = _evidence(
        "e-available-only",
        "technical_tool",
        "candidate:tools",
        "candidate_profile_fact",
        "Legacy CRM",
    )
    return ApplicationContext(
        candidate_id="candidate-a",
        job_id="job-1",
        analysis_id="analysis-1",
        contract_signature="contract-signature",
        job_title="Product Operations Specialist",
        company="Target Ltd",
        role_family="Product Operations",
        job_level="Intermediate",
        core_requirements=["SQL", "Process improvement"],
        direct_evidence=[direct, proven],
        transferable_evidence=[transferable],
        supporting_evidence=[supporting],
        developing_evidence=[developing],
        available_evidence=[
            direct,
            proven,
            transferable,
            supporting,
            developing,
            irrelevant,
        ],
        development_gaps=["Advanced reporting"],
        structural_gaps=["Production Kubernetes ownership"],
        source_signature="context-signature",
    )


def _statement(text, claim_type, refs):
    return TailoredCVStatement(
        text=text,
        claim_type=claim_type,
        evidence_refs=list(refs),
    )


def _draft():
    return DraftTailoredCV(
        candidate_id="candidate-a",
        job_id="job-1",
        application_context_signature="context-signature",
        headline=_statement("Operations specialist", "summary", ["e-proven"]),
        professional_summary=[
            _statement(
                "Experienced in process improvement",
                "summary",
                ["e-proven"],
            )
        ],
        key_skills=[_statement("SQL", "skill", ["e-skill"])],
        experiences=[
            DraftTailoredCVExperience(
                source_experience_id="experience-1",
                company="Example Ltd",
                role="Operations Specialist",
                bullets=[
                    _statement(
                        "Managed support escalations",
                        "professional_experience",
                        ["e-direct"],
                    )
                ],
            )
        ],
        additional_relevant_information=[
            _statement(
                "Stakeholder communication",
                "transferable_capability",
                ["e-transferable"],
            ),
            _statement(
                "Developing Kubernetes knowledge",
                "developing_knowledge",
                ["e-developing"],
            ),
        ],
    )


def _codes(result):
    return {item.code for item in result.issues}


def test_valid_cv_draft_passes_and_retains_protected_gaps():
    result = validate_tailored_cv_draft(_draft(), _context())

    assert result.valid is True
    assert result.issues == []
    assert result.draft_signature
    assert result.protected_structural_gaps == [
        "Production Kubernetes ownership"
    ]


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("candidate_id", "candidate-b", "candidate_mismatch"),
        ("job_id", "job-2", "job_mismatch"),
        (
            "application_context_signature",
            "wrong-signature",
            "context_signature_mismatch",
        ),
    ],
)
def test_identity_and_context_mismatches_are_rejected(field, value, code):
    result = validate_tailored_cv_draft(
        replace(_draft(), **{field: value}),
        _context(),
    )

    assert result.valid is False
    assert code in _codes(result)


def test_statement_without_evidence_is_rejected():
    draft = replace(
        _draft(),
        headline=_statement("Operations specialist", "summary", []),
    )

    assert "missing_evidence_ref" in _codes(
        validate_tailored_cv_draft(draft, _context())
    )


def test_unknown_evidence_ref_is_rejected():
    draft = replace(
        _draft(),
        headline=_statement("Operations specialist", "summary", ["unknown"]),
    )

    assert "unknown_evidence_ref" in _codes(
        validate_tailored_cv_draft(draft, _context())
    )


def test_correct_professional_experience_provenance_passes():
    result = validate_tailored_cv_draft(_draft(), _context())

    assert "experience_source_mismatch" not in _codes(result)


def test_wrong_experience_source_is_rejected():
    experience = replace(
        _draft().experiences[0],
        source_experience_id="experience-2",
    )
    draft = replace(_draft(), experiences=[experience])

    assert "experience_source_mismatch" in _codes(
        validate_tailored_cv_draft(draft, _context())
    )


def test_non_experience_ref_cannot_support_experience_bullet():
    experience = replace(
        _draft().experiences[0],
        bullets=[
            _statement(
                "Used SQL professionally",
                "professional_experience",
                ["e-skill"],
            )
        ],
    )
    result = validate_tailored_cv_draft(
        replace(_draft(), experiences=[experience]),
        _context(),
    )

    assert "experience_source_mismatch" in _codes(result)
    assert "insufficient_evidence_authority" in _codes(result)


def test_developing_evidence_cannot_support_professional_claim():
    draft = replace(
        _draft(),
        headline=_statement(
            "Production Kubernetes owner",
            "professional_experience",
            ["e-developing"],
        ),
    )

    assert "developing_evidence_overclaim" in _codes(
        validate_tailored_cv_draft(draft, _context())
    )


def test_mixed_evidence_cannot_hide_developing_overclaim():
    draft = replace(
        _draft(),
        headline=_statement(
            "Production Kubernetes owner",
            "professional_experience",
            ["e-direct", "e-developing"],
        ),
    )

    assert "developing_evidence_overclaim" in _codes(
        validate_tailored_cv_draft(draft, _context())
    )


def test_transferable_evidence_cannot_be_direct_experience():
    draft = replace(
        _draft(),
        headline=_statement(
            "Specialized stakeholder lead",
            "professional_experience",
            ["e-transferable"],
        ),
    )

    assert "transferable_evidence_overclaim" in _codes(
        validate_tailored_cv_draft(draft, _context())
    )


def test_explicit_protected_gap_conflict_is_rejected():
    draft = replace(
        _draft(),
        headline=_statement(
            "Production Kubernetes ownership",
            "summary",
            ["e-developing"],
        ),
    )

    assert "protected_gap_conflict" in _codes(
        validate_tailored_cv_draft(draft, _context())
    )


def test_protected_gap_detects_explicit_ownership_word_form():
    draft = replace(
        _draft(),
        headline=_statement(
            "Owned production Kubernetes infrastructure",
            "summary",
            ["e-developing"],
        ),
    )

    assert "protected_gap_conflict" in _codes(
        validate_tailored_cv_draft(draft, _context())
    )


@pytest.mark.parametrize(
    ("statement", "code"),
    [
        (_statement("", "summary", ["e-proven"]), "empty_statement"),
        (_statement("Operations", "unsupported", ["e-proven"]), "invalid_claim_type"),
    ],
)
def test_invalid_statement_structure_is_rejected(statement, code):
    draft = replace(_draft(), headline=statement)

    assert code in _codes(validate_tailored_cv_draft(draft, _context()))


def test_duplicate_evidence_refs_are_normalized():
    draft = replace(
        _draft(),
        headline=_statement(
            " Operations specialist ",
            "summary",
            ["e-proven", " e-proven ", "e-proven"],
        ),
    )
    result = validate_tailored_cv_draft(draft, _context())

    assert result.valid is True
    assert result.normalized_draft.headline.evidence_refs == ["e-proven"]
    assert result.normalized_draft.headline.text == "Operations specialist"


def test_generation_request_contains_selected_evidence_only():
    request = build_tailored_cv_generation_request(_context())
    refs = {item["evidence_ref"] for item in request.selected_evidence}

    assert refs == {
        "e-direct",
        "e-proven",
        "e-transferable",
        "e-skill",
        "e-developing",
    }
    assert "e-available-only" not in refs
    assert request.protected_structural_gaps == [
        "Production Kubernetes ownership"
    ]
    assert request.application_context_signature == "context-signature"


def test_draft_signature_is_deterministic_and_changes_with_content():
    first = validate_tailored_cv_draft(_draft(), _context())
    duplicate = validate_tailored_cv_draft(_draft(), _context())
    changed = replace(
        _draft(),
        headline=_statement("Changed headline", "summary", ["e-proven"]),
    )
    changed_result = validate_tailored_cv_draft(changed, _context())

    assert first.draft_signature == duplicate.draft_signature
    assert first.draft_signature != changed_result.draft_signature
