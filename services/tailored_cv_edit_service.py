from dataclasses import dataclass, field
from copy import deepcopy

from services.tailored_cv_truth_guard import validate_tailored_cv_draft
from services.cv_keyword_coverage import check_ats_keyword_coverage


@dataclass(frozen=True)
class EditedCVValidationResult:
    accepted: bool
    cv: object
    issues: list = field(default_factory=list)
    keyword_coverage: dict = field(default_factory=dict)


def validate_edited_cv(*, draft, context):
    validation = validate_tailored_cv_draft(draft, context, require_text_grounding=True)
    # Validation never replaces the user's document with normalized or repaired text.
    return EditedCVValidationResult(validation.valid, deepcopy(draft), list(validation.issues),
                                    check_ats_keyword_coverage(draft, context))
