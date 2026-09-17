"""Source-backed version/change boundaries. No clock, age cutoff or semantic matcher."""
from datetime import date

from models.hiring_case import TemporalRequirement as Requirement, TemporalApplicability as Applicability
from models.profile_interpretation import InterpretationAuthority


def _date(value):
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        raise ValueError("invalid_temporal_metadata") from None


def validate_temporal_requirement(need, hard_facts):
    required = {fact.fact_id: fact for fact in hard_facts.facts
                if fact.temporal_requirement is Requirement.CURRENT_REQUIRED
                and fact.temporal_need_id == need.need_id}
    supplied = set(need.temporal_requirement_refs)
    if need.temporal_requirement is Requirement.NOT_REQUIRED:
        if required or supplied:
            raise ValueError("unsupported_temporal_requirement")
        return ()
    if (need.authority is not InterpretationAuthority.EXPLICIT or not supplied
            or supplied != set(required) or not supplied <= set(need.hard_fact_refs)):
        raise ValueError("unsupported_temporal_requirement")
    for fact in required.values():
        _date(fact.material_change_on)
        if fact.required_version and fact.required_version in fact.superseded_versions:
            raise ValueError("invalid_temporal_metadata")
    return tuple(required.values())


def resolve_temporal_applicability(need, hard_facts, evidence_refs, metadata):
    facts = validate_temporal_requirement(need, hard_facts)
    if not facts:
        return Applicability.NOT_APPLICABLE
    relevant = [item for item in metadata if item.ref in evidence_refs and item.need_id == need.need_id]
    if len({item.ref for item in relevant}) != len(relevant):
        raise ValueError("invalid_temporal_metadata")
    outcomes = []
    for fact in facts:
        values = []
        for item in relevant:
            performed = _date(item.performed_on)
            changed = _date(fact.material_change_on)
            if fact.required_version and item.version == fact.required_version:
                # Contradictory current-version/pre-change metadata is not proof of currency.
                value = Applicability.UNKNOWN if performed and changed and performed < changed else Applicability.SATISFIED
            elif item.version and item.version in fact.superseded_versions:
                value = Applicability.NOT_SATISFIED
            elif performed and changed and performed < changed:
                value = Applicability.NOT_SATISFIED
            else:
                # A date alone after a change does not prove use of the new procedure.
                value = Applicability.UNKNOWN
            values.append(value)
        if Applicability.SATISFIED in values:
            outcomes.append(Applicability.SATISFIED)
        elif values and all(item is Applicability.NOT_SATISFIED for item in values):
            outcomes.append(Applicability.NOT_SATISFIED)
        else:
            outcomes.append(Applicability.UNKNOWN)
    if Applicability.NOT_SATISFIED in outcomes:
        return Applicability.NOT_SATISFIED
    if all(item is Applicability.SATISFIED for item in outcomes):
        return Applicability.SATISFIED
    return Applicability.UNKNOWN
