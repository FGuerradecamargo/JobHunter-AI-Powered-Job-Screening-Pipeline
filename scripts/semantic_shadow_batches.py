"""Frozen synthetic Batch 002 inputs. Reference judgments never enter requests."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from models.hiring_case import EvidenceRequirement, RequirementImportance
from models.profile_interpretation import HardJobFact
from models.semantic_evidence import SemanticSupportRelation, SemanticCoverage
from models.structured_interpretation import RegisteredSourceRef, SourceRefClass
from tests.semantic_evidence_v1_runner import project

BATCH_002_IDS = ('SE03', 'SE04', 'SE13', 'SE14', 'SE18', 'SE19', 'SE40', 'SE44', 'SE55', 'AV06', 'AV02', 'AV26')
BATCH_002_HASH = '78a7835606acd9ca8becabc2537824fab07650b8fb6f0383e622f5afaac0335e'


def batch_002_cases():
    raw = Path(__file__).with_name('semantic_shadow_batch_002.json').read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != BATCH_002_HASH:
        raise ValueError('frozen_batch_changed')
    data = json.loads(raw)
    if tuple(c['id'] for c in data['cases']) != BATCH_002_IDS or data['maximum_requests'] != 12:
        raise ValueError('invalid_frozen_batch')
    return data['cases']


def selected_batch_002_case(case_id):
    case = next(c for c in batch_002_cases() if c['id'] == case_id)
    request = project(dict(id=case_id, source_refs=[e['ref'] for e in case['evidence']],
        candidate_evidence=[e['text'] for e in case['evidence']], confirmed_absence=False,
        job_need=case['needs'][0]['text']))
    # These are synthetic statements, not proof of professional context from provenance.
    request = replace(request, evidence=tuple(replace(e, source_type='career_update') for e in request.evidence))
    context = replace(request.context, source_registry=tuple(replace(r, source_type='career_update')
        if r.ref in {e.ref for e in request.evidence} else r for r in request.context.source_registry))
    facts, needs, registry = [], [], [r for r in context.source_registry if r.ref != 'fact']
    for index, item in enumerate(case['needs']):
        fact_id = 'fact' if index == 0 else 'fact_' + str(index)
        constraint = EvidenceRequirement.DIRECT_REQUIRED if item['direct_required'] else EvidenceRequirement.DEFENSIBLE
        facts.append(HardJobFact(fact_id, 'requirement', item['text'], 'job-source',
            evidence_requirement=constraint, constraint_need_id=item['id'] if item['direct_required'] else ''))
        needs.append(replace(context.job_profile.needs[0], need_id=item['id'], label=item['text'],
            importance=RequirementImportance(item['importance']), hard_fact_refs=(fact_id,),
            evidence_requirement=constraint, evidence_requirement_refs=(fact_id,) if item['direct_required'] else ()))
        registry.append(RegisteredSourceRef(fact_id, SourceRefClass.JOB_HARD_FACT, 'job', 'job_description'))
    context = replace(context, hard_facts=replace(context.hard_facts, facts=tuple(facts)),
        job_profile=replace(context.job_profile, needs=tuple(needs)), source_registry=tuple(registry))
    return replace(request, context=context), {n['id']: (SemanticSupportRelation(n['expected'][0]),
        SemanticCoverage(n['expected'][1])) for n in case['needs']}
