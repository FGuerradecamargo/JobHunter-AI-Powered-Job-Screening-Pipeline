from dataclasses import asdict, dataclass

from models.hiring_case import HiringCaseClassification
from models.hiring_case import HiringCase, RequirementEvidenceState
from models.hiring_case import HIRING_CASE_SCHEMA_VERSION
from services.structured_interpretation_validation import decode_structure
import json


def read_hiring_case(analysis, *, candidate_id, job_id):
    """Fail closed for legacy, corrupt or differently scoped persisted analyses."""
    try:
        if isinstance(analysis, str):
            analysis = json.loads(analysis)
        case = decode_structure(analysis["hiring_case"], HiringCase)
        if (case.authority != "deterministic_hiring_case" or case.schema_version != HIRING_CASE_SCHEMA_VERSION
                or case.candidate_id != candidate_id or case.job_id != job_id):
            return None
        return case
    except (ValueError, TypeError, KeyError):
        return None


def hiring_case_analysis(case: HiringCase) -> dict:
    """One-way display/storage projection. It cannot independently classify."""
    bucket = {
        HiringCaseClassification.BEST_MATCH: "best_match",
        HiringCaseClassification.WORTH_A_TRY: "potential",
        HiringCaseClassification.YOURE_STRONG_BUT: "good_opportunity",
    }.get(case.classification, "reject")
    supported = [item.requirement for item in case.requirements
                 if item.evidence_state in {RequirementEvidenceState.PROVEN, RequirementEvidenceState.TRANSFERABLE}]
    missing = [item.requirement for item in case.requirements
               if item.evidence_state is RequirementEvidenceState.EVIDENCE_MISSING]
    return {
        "job_id": case.job_id, "recommendation": bucket, "bucket": bucket,
        "hiring_case": asdict(case), "authority": case.authority,
        "classification": case.classification.value, "surfacing_reason": case.surfacing_reason,
        "competitive_status": case.hiring_case_strength.value,
        "current_fit": None, "growth_value": None,
        "core_requirements": [item.requirement for item in case.requirements],
        "requirements_met": supported, "strengths": supported,
        "development_gaps": missing, "hard_conflicts": list(case.hard_eligibility_blockers),
        "reason": case.surfacing_reason, "final_reason": case.surfacing_reason,
        "tailored_cv": None, "interview_prep": None,
    }


LEGACY_RECOMMENDATION_MAP = {
    "best_match": HiringCaseClassification.BEST_MATCH,
    "potential": HiringCaseClassification.WORTH_A_TRY,
    "good_opportunity": HiringCaseClassification.YOURE_STRONG_BUT,
    "competitive": HiringCaseClassification.YOURE_STRONG_BUT,
}


@dataclass(frozen=True)
class LegacyClassificationView:
    original_recommendation: str
    display_classification: HiringCaseClassification | None
    source_schema_version: str = "legacy-analysis"
    produced_by_hiring_case_engine: bool = False


def read_legacy_classification(recommendation: str) -> LegacyClassificationView:
    original = str(recommendation or "").strip().casefold()
    return LegacyClassificationView(
        original_recommendation=original,
        display_classification=LEGACY_RECOMMENDATION_MAP.get(original),
    )
