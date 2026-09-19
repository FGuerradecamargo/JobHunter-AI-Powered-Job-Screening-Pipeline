import io
import json
from pathlib import Path
import hashlib
import pytest

from scripts.run_semantic_ai_shadow import main
from scripts.semantic_shadow_batches import BATCH_002_IDS, batch_002_cases, selected_batch_002_case
from services.ai.semantic_shadow_request import PROMPT_VERSION, INSTRUCTIONS
from services.ai.openai_semantic_interpreter import SemanticShadowConfig, SemanticTransportReply
from tests.test_openai_semantic_shadow import adapter, wire


def forbidden(*args, **kwargs):
    raise AssertionError('No external IO')


@pytest.mark.parametrize('args', [[], ['--batch', 'batch-002']])
def test_dry_runs_never_construct_transport(args):
    out = io.StringIO()
    assert main(args, config=SemanticShadowConfig(True, 'fake-model'), transport_factory=forbidden, output=out) == 0
    plan = json.loads(out.getvalue())
    assert plan['executed_requests'] == 0 and plan['store'] is False
    assert plan['prompt_version'] == 'semantic-support-prompt-v2'
    assert plan['planned_requests'] == (12 if args else 8)


@pytest.mark.parametrize('enabled,args', [(False, ['--live', '--confirm-external-ai']), (True, ['--live'])])
def test_batch_double_lock(enabled, args):
    assert main(['--batch', 'batch-002', *args], config=SemanticShadowConfig(enabled, 'fake'),
        transport_factory=forbidden, output=io.StringIO()) == 2


def test_frozen_batch_and_corrected_facts():
    assert tuple(c['id'] for c in batch_002_cases()) == BATCH_002_IDS
    request, refs = selected_batch_002_case('AV06')
    assert request.evidence[0].summary.startswith('Independently traced')
    assert refs['tax'][0].value == 'none'
    request, _ = selected_batch_002_case('AV02')
    assert request.context.job_profile.needs[1].evidence_requirement.value == 'direct_required'
    root = Path(__file__).parents[1]
    original = json.loads((root / 'scripts/semantic_shadow_first_batch.json').read_text())
    assert original['maximum_requests'] == 8
    assert original['case_ids'] == ['SE01', 'SE03', 'SE05', 'SE10', 'AV06', 'SE13', 'SE31', 'SE02']


@pytest.mark.parametrize('case_id,relation,coverage', [('SE03','adjacent','full'), ('SE04','adjacent','partial'),
    ('SE13','adjacent','partial'), ('SE14','adjacent','partial'), ('SE55','direct','partial')])
def test_reviewed_shapes_pass_fake_adapter(case_id, relation, coverage):
    req, _ = selected_batch_002_case(case_id)
    obj, transport, _ = adapter(wire(req, relation, coverage), req=req)
    run = obj.evaluate(req, allow_external_ai=True)
    assert run.failure is None
    assert run.result.needs[0].assessment.value == ('transferable' if coverage == 'full' else 'evidence_missing')
    assert transport.calls[0]['store'] is False
    assert run.metadata.prompt_version == PROMPT_VERSION


def test_reviewed_instructions_and_returned_model():
    assert 'Coverage is NOT a similarity score' in INSTRUCTIONS
    assert 'Missing proof is NOT a confirmed GAP' in INSTRUCTIONS
    req, _ = selected_batch_002_case('SE55')
    obj, _, _ = adapter(req=req, reply=SemanticTransportReply('completed', json.dumps(wire(req)), returned_model='fake-2026'))
    assert obj.evaluate(req, allow_external_ai=True).metadata.returned_model == 'fake-2026'
