"""Offline sensitivity replay of reported pairs, not reconstruction of unknown provider links."""
from dataclasses import asdict, replace
import json
from pathlib import Path

from scripts.semantic_shadow_batches import BATCH_002_IDS, selected_batch_002_case
from models.profile_interpretation import HiringCaseInterpretation, HardJobFact
from models.hiring_case import OpportunitySignal, OpportunitySignalKind, OpportunitySignalState, RequirementImportance
from services.semantic_evidence_boundary import signature, validate_semantic_support, semantic_requirement_links
from services.profile_hiring_case_adapter import build_profile_hiring_case_input
from services.hiring_case_engine import build_hiring_case


def observed_cases():
    data = json.loads(Path(__file__).with_name('fixtures').joinpath('semantic_shadow_batch_002_observed.json').read_text())
    if tuple(c['id'] for c in data['cases']) != BATCH_002_IDS:
        raise ValueError('observation_case_mismatch')
    return {c['id']: c['needs'] for c in data['cases']}


def reconstructed_response(case_id, request, pairs):
    """Links/known confidence are fixed replay assumptions, NOT claimed historical observations."""
    needs = []
    version = 'batch-002-pair-replay-v1'
    for need in request.context.job_profile.needs:
        relation, coverage = pairs[need.need_id]
        reason = 'no_support' if relation == 'none' else ('partial_support' if coverage == 'partial' else relation + '_support')
        # AV02 has separate recovery and release sources. AV06 deliberately reuses recovery.
        refs = (['e1'] if need.need_id == 'release' else ['e0']) if case_id == 'AV02' else [e.ref for e in request.evidence]
        needs.append(dict(need_id=need.need_id, support_relation=relation, coverage=coverage,
            confidence='high', reason_code=reason, joint_support=False, links=[dict(
                need_id=need.need_id, evidence_ref=ref, candidate_capability_id=None,
                support_relation=relation, coverage=coverage, confidence='high', reason_code=reason,
                interpreter_version=version) for ref in refs]))
    return dict(input_signature=signature(request), interpreter_version=version, needs=needs)


def replay(case_id, pairs, *, value_context=None, blocker=False):
    request, _ = selected_batch_002_case(case_id)
    if blocker:
        context = request.context
        hard = replace(context.hard_facts, facts=(*context.hard_facts.facts,
            HardJobFact('synthetic-blocker','eligibility','Synthetic hard blocker','job-source',hard_blocker=True)))
        from models.structured_interpretation import RegisteredSourceRef, SourceRefClass
        request = replace(request, context=replace(context, hard_facts=hard,
            source_registry=(*context.source_registry, RegisteredSourceRef('synthetic-blocker', SourceRefClass.JOB_HARD_FACT,'job','job_description'))))
    raw = reconstructed_response(case_id,request,pairs)
    semantic = validate_semantic_support(request,raw)
    if semantic.status.value not in ('accepted','normalized'):
        raise ValueError(('invalid_replay',semantic.issue_codes))
    signals = ()
    if value_context:
        state, importance = {'high':('positive','core'), 'medium':('negative','important'), 'low':('negative','core')}[value_context]
        signals = (OpportunitySignal(OpportunitySignalKind.CAREER_DIRECTION, OpportunitySignalState(state),
            RequirementImportance(importance), 'Fixed synthetic sensitivity control, not Batch 002 evidence'),)
    data = build_profile_hiring_case_input(candidate_profile=request.context.candidate_profile,
        job_profile=request.context.job_profile, hard_facts=request.context.hard_facts,
        interpretation=HiringCaseInterpretation(semantic_requirement_links(request,raw),opportunity_signals=signals))
    result = build_hiring_case(data)
    return dict(semantic={s.support.need_id:dict(relation=s.support.support_relation.value,
        coverage=s.support.coverage.value, assessment=s.assessment.value, supporting_refs=list(s.supporting_refs)) for s in semantic.needs},
        requirements={r.requirement_id:dict(assessment=r.evidence_state.value,
            evidence_requirement=r.evidence_requirement.value, satisfied=r.constraint_satisfied,
            reason=r.constraint_reason_code.value, temporal_requirement=r.temporal_requirement.value,
            temporal_result=r.temporal_applicability.value) for r in result.requirements},
        strength=result.hiring_case_strength.value, blockers=result.hard_eligibility_blockers,
        eligibility='blocked' if result.hard_eligibility_blockers else 'no_known_blocker',
        value=result.opportunity.value.value, value_confidence=result.opportunity.confidence.value,
        category=result.classification.value, how_to_prove=asdict(result.how_to_prove),
        add_evidence=[asdict(a) for a in result.add_evidence])


def compare_all(*, value_context=None, blocker=False):
    observed = observed_cases()
    rows = []
    for case_id in BATCH_002_IDS:
        _, expected = selected_batch_002_case(case_id)
        reference = {k: (v[0].value,v[1].value) for k,v in expected.items()}
        a = replay(case_id,reference,value_context=value_context,blocker=blocker)
        b = replay(case_id,observed[case_id],value_context=value_context,blocker=blocker)
        changed = [key for key in a if a[key] != b[key]]
        # Requirement satisfaction and proof actions are product decisions, even with the same category.
        decisions = {'requirements','strength','blockers','eligibility','value','category','how_to_prove','add_evidence'}
        impact = 'PRODUCT_DECISION_CHANGE' if decisions.intersection(changed) else ('EXPLANATION_ONLY' if changed else 'NO_PRODUCT_IMPACT')
        rows.append(dict(case_id=case_id, reference=a, observed_real_ai=b, changed=changed, impact=impact))
    return rows


def report():
    rows = compare_all()
    relation = coverage = both = total = 0
    for row in rows:
        for key,a in row['reference']['semantic'].items():
            b = row['observed_real_ai']['semantic'][key]
            r,c = a['relation'] == b['relation'], a['coverage'] == b['coverage']
            total += 1
            relation += r
            coverage += c
            both += r and c
    return dict(total=total,relation_agreement=relation,coverage_agreement=coverage,dual_axis_agreement=both,rows=rows)


if __name__ == '__main__':
    print(json.dumps(report(), indent=2))
