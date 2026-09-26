from dataclasses import dataclass
from enum import Enum


class CVPreparationStage(str, Enum):
    MATCHING_EVIDENCE = "matching_evidence"
    ADAPTING_LANGUAGE = "adapting_language"
    CHECKING_ATS_KEYWORDS = "checking_ats_keywords"
    KEEPING_DEFENSIBLE = "keeping_defensible"


class CVPreparationStageState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True)
class CVPreparationProgress:
    stage: CVPreparationStage
    state: CVPreparationStageState
    label: str


STAGE_LABELS = {
    CVPreparationStage.MATCHING_EVIDENCE:
        "Matching your strongest evidence",
    CVPreparationStage.ADAPTING_LANGUAGE:
        "Adapting language to the role",
    CVPreparationStage.CHECKING_ATS_KEYWORDS:
        "Checking ATS keywords",
    CVPreparationStage.KEEPING_DEFENSIBLE:
        "Keeping everything defensible",
}


def progress_event(stage, state):
    return CVPreparationProgress(
        stage=stage,
        state=state,
        label=STAGE_LABELS[stage],
    )
