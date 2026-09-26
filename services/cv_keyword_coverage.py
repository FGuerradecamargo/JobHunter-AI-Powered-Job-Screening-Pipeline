"""Informational terminology coverage, never evidence creation."""
import re
from services.tailored_cv_truth_guard import _all_statement_locations


def _contains(text, term):
    return bool(re.search(r"(?<!\w)" + re.escape(" ".join(term.casefold().split())) + r"(?!\w)",
                          " ".join(text.casefold().split())))


def check_ats_keyword_coverage(cv, context):
    text = " ".join(statement.text for _, statement, _ in _all_statement_locations(cv))
    result = {"matched": [], "missing_with_evidence": [], "missing_without_evidence": []}
    for term in dict.fromkeys(str(v).strip() for v in context.core_requirements):
        if not term:
            continue
        if _contains(text, term):
            result["matched"].append(term)
        elif any(_contains(e.statement, term) for e in context.available_evidence):
            result["missing_with_evidence"].append(term)
        else:
            result["missing_without_evidence"].append(term)
    return result
