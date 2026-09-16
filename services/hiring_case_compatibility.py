from dataclasses import dataclass

from models.hiring_case import HiringCaseClassification


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
