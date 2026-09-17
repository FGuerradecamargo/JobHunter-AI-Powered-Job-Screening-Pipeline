"""Validate explicit source-layer constraints without interpreting job prose."""
from models.hiring_case import EvidenceRequirement
from models.profile_interpretation import InterpretationAuthority


def validate_evidence_requirement(need, hard_facts):
    facts = {fact.fact_id: fact for fact in hard_facts.facts}
    if len(facts) != len(hard_facts.facts):
        raise ValueError("unsupported_direct_evidence_requirement")
    required = {fact.fact_id for fact in hard_facts.facts
                if fact.evidence_requirement is EvidenceRequirement.DIRECT_REQUIRED
                and fact.constraint_need_id == need.need_id}
    supplied = set(need.evidence_requirement_refs)
    if need.evidence_requirement is EvidenceRequirement.DEFENSIBLE:
        if required or supplied:
            raise ValueError("unsupported_direct_evidence_requirement")
        return
    if (need.authority is not InterpretationAuthority.EXPLICIT or not supplied
            or not supplied <= required or not supplied <= set(need.hard_fact_refs)):
        raise ValueError("unsupported_direct_evidence_requirement")
