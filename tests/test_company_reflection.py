import copy
import json
from dataclasses import asdict
from types import SimpleNamespace
import pytest
from models.company_interview import (QUESTIONS, FINAL_QUESTION, ADAPTIVE_QUESTIONS,
    VERSION, V1_VERSION, V1_QUESTIONS, ConfirmedCompanyAnswer, validate_answers)
from services.company_interview import (answer, process, review_reflection,
    current_question, confirmed_answers)
from services.company_reflection import (reflection_request, build_reflection_prompt,
    parse_reflection, reflect, FIELDS, ReflectionUnavailable)
from services.ai.voice_transcription import VoiceConfig
from tests.company_interview_fakes import FakeReflection, SCENARIOS, response
from tests.test_company_interview import draft, complete, Provider, wav, UI, Rerun
from components.company_interview import render_company_interview

CONFIG = VoiceConfig(True, True, 'fake')


def ready_core(scenario='support'):
    d = draft()
    for text in SCENARIOS[scenario]:
        answer(d, 'scope', 'text', text)
    process(d, 'scope', Provider(), CONFIG, authorized=True)
    return d


def test_exact_v2_questions():
    assert QUESTIONS == (
        'When I get in tomorrow, what do I do first?',
        'And then? Take me through how the day usually goes from there.',
        'Who am I usually dealing with during the day, and what do they normally need from me?',
        'When something goes wrong, what usually happens? What do I do first? If an example comes to mind, tell me about it :D',
        'What am I actually going to use to do the job — systems, tools, machines, documents, equipment, whatever it is? Which ones do I really need to know, and what do I use them for?',
        'How do I know I’m doing the job right? What do people actually look at, check, measure or care about?',
        'What can I normally decide or fix on my own, and when do I need to bring someone else in?',
        'At the end of a good day, what have I actually got done? What would still be sitting there if I hadn’t done my job?',
    )


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_synthetic_scenarios_reflect_text_only(scenario):
    d = ready_core(scenario)
    p = FakeReflection('concrete_evidence' if scenario == 'concise' else None)
    assert reflect(d, 'scope', p, authorized=True)
    request = json.loads(p.prompts[0].split('SOURCE DATA:\n')[1])
    assert set(request) == {'company', 'start_date', 'end_date', 'sources'}
    assert len(request['sources']) == 8
    assert all(set(a) == {'question_id', 'question_text', 'text', 'skipped'} for a in request['sources'])
    assert not any(word in json.dumps(request) for word in ('audio', 'candidate_id', 'scope'))
    assert not any('reflection' in a for a in d['answers'])
    if scenario == 'support':
        output = json.dumps(d['reflection'])
        assert 'Occasional SQL use, not established expertise.' in output
        assert 'leadership' not in output and '99%' not in output
        assert all(d['reflection']['interpretation'][f] for f in FIELDS)
    if scenario in ('electrician', 'nurse', 'warehouse'):
        assert 'equipment' in request['sources'][4]['question_text']


@pytest.mark.parametrize('mutation', [
    lambda d: d.update(adaptive_question='Unreviewed arbitrary question?'),
    lambda d: d.update(material_missing_dimension=['context', 'core_work']),
    lambda d: d.update(material_missing_dimension='context'),
    lambda d: d['coverage'].update(context='UNKNOWN'),
    lambda d: d['coverage'].update(context=True),
    lambda d: d['coverage'].pop('context'),
    lambda d: d['interpretation'].update(concept_ids=['invented']),
    lambda d: d['interpretation']['understood'][0].update(seniority='Director'),
    lambda d: d['interpretation']['understood'][0].update(support=[]),
    lambda d: d['interpretation']['understood'][0]['support'][0].update(question_id='q99'),
    lambda d: d['interpretation']['understood'][0]['support'][0].update(quote='invented achievement'),
    lambda d: d['interpretation']['understood'][0].update(uncertainty=''),
])
def test_malformed_or_ungrounded_reflection_rejected(mutation):
    request = reflection_request(ready_core())
    data = response(request)
    mutation(data)
    with pytest.raises(ValueError, match='reflection_contract_invalid'):
        parse_reflection(json.dumps(data), request)


def test_skipped_source_cannot_support_claim():
    d = ready_core()
    request = reflection_request(d)
    data = response(request)
    request['sources'][0]['skipped'] = True
    with pytest.raises(ValueError):
        parse_reflection(json.dumps(data), request)


@pytest.mark.parametrize('status', ['SUFFICIENT', 'PARTIAL', 'INSUFFICIENT'])
def test_no_selected_material_dimension_means_no_adaptive(status):
    d = ready_core()
    assert reflect(d, 'scope', FakeReflection(status=status), authorized=True)
    review_reflection(d, 'scope', "It's BPO, not PPO. I check logs and the backend.")
    assert d['stage'] == 'final'
    assert current_question(d)[1] == FINAL_QUESTION
    answer(d, 'scope', 'skip')
    records = confirmed_answers(d, 'scope')
    assert len(records) == 10  # Nine questions plus a correction, not a tenth question.
    assert records[-2].source_kind == 'REVIEW_CORRECTION'
    assert records[-1].source_kind == 'FINAL_OPEN'
    assert all(a.interview_version == VERSION for a in records)
    assert records[0].confirmed_text == SCENARIOS['support'][0]


@pytest.mark.parametrize('dimension', ADAPTIVE_QUESTIONS)
def test_one_approved_adaptive_then_final(dimension):
    d = ready_core('concise')
    assert reflect(d, 'scope', FakeReflection(dimension), authorized=True)
    review_reflection(d, 'scope')
    assert current_question(d) == ('adaptive_' + dimension, ADAPTIVE_QUESTIONS[dimension], 'ADAPTIVE_QUESTION')
    answer(d, 'scope', 'text', 'Additional stated fact.')
    assert current_question(d)[1] == FINAL_QUESTION
    answer(d, 'scope', 'text', 'Final memory.')
    records = confirmed_answers(d, 'scope')
    assert len(records) == 10
    assert sum(a.source_kind == 'ADAPTIVE_QUESTION' for a in records) == 1
    with pytest.raises(ValueError):
        review_reflection(d, 'scope')
    with pytest.raises(ValueError):
        answer(d, 'scope', 'text', 'No eleventh question')


def test_extra_voice_answers_processed_separately_never_repeat_core():
    d, p = draft(), Provider()
    complete(d)
    assert not p.calls
    process(d, 'scope', p, CONFIG, authorized=True)
    rp = FakeReflection('concrete_evidence')
    assert reflect(d, 'scope', rp, authorized=True)
    review_reflection(d, 'scope')
    answer(d, 'scope', 'voice', wav())
    assert len(p.calls) == 8 and d['stage'] == 'finish_extra'
    process(d, 'scope', p, CONFIG, authorized=True)
    assert len(p.calls) == 9 and p.calls[-1][1]['question_id'] == 'adaptive_concrete_evidence'
    answer(d, 'scope', 'voice', wav())
    assert len(p.calls) == 9
    p.fail = 'final'
    process(d, 'scope', p, CONFIG, authorized=True)
    assert d['stage'] == 'failed' and len(p.calls) == 10
    p.fail = None
    process(d, 'scope', p, CONFIG, authorized=True)
    assert len(p.calls) == 11 and d['stage'] == 'review'
    assert len(rp.prompts) == 1
    assert [m['question_id'] for _, m, _ in p.calls].count('q1') == 1


def test_reflection_failure_is_explicit_and_never_retranscribes(caplog):
    d = ready_core()
    original = copy.deepcopy(d['answers'])
    p = FakeReflection(fail=True)
    with pytest.raises(ValueError):
        reflect(d, 'scope', p)
    assert not p.prompts
    assert not reflect(d, 'scope', p, authorized=True)
    assert d['stage'] == 'reflection_failed' and d['answers'] == original
    assert len(p.prompts) == 1
    inputs = SimpleNamespace(config=CONFIG, provider=Provider(), events=None)
    ui = UI()
    render_company_interview(d, 'scope', None, inputs, ui, p)
    assert 'Retry reflection' in ui.buttons and not ui.audio_labels
    assert not inputs.provider.calls and len(p.prompts) == 1
    p.fail = False
    with pytest.raises(Rerun):
        render_company_interview(d, 'scope', None, inputs, UI('Retry reflection'), p)
    assert len(p.prompts) == 2 and not inputs.provider.calls
    assert 'PRIVATE' not in caplog.text


def test_unconfigured_reflection_does_not_fabricate_and_final_still_shown():
    d = ready_core()
    assert not reflect(d, 'scope', ReflectionUnavailable(), authorized=True)
    inputs = SimpleNamespace(config=CONFIG, provider=Provider(), events=None)
    with pytest.raises(Rerun):
        render_company_interview(d, 'scope', None, inputs, UI('Continue with my source answers'))
    assert current_question(d)[1] == FINAL_QUESTION and 'reflection' not in d


def test_v1_history_and_v2_sources_survive_additive_migration():
    from services.database import get_connection, create_company_interview_schema
    from services.candidate_repository import CandidateRepository
    from services.candidate_onboarding_repository import CandidateOnboardingRepository
    from models.candidate import Candidate
    CandidateRepository().save(Candidate('c', 'Synthetic', '', '', ''))
    repo = CandidateOnboardingRepository()
    old = [ConfirmedCompanyAnswer(f'q{i+1}', text, 'text', 'Legacy statement', False,
        V1_VERSION, V1_VERSION) for i, text in enumerate(V1_QUESTIONS)]
    validate_answers(old)
    kw = dict(candidate_id='c', company='Legacy Company', start_date='2020-01', end_date=None)
    repo.confirm_company_interview(**kw, answers=old, experience_id='old')
    with get_connection() as conn:
        conn.execute('ALTER TABLE company_interview_answers DROP COLUMN source_kind')
        create_company_interview_schema(conn)
        create_company_interview_schema(conn)
    restored = repo.list_company_answers('c', 'old')
    assert restored == old and all(a.interview_version == V1_VERSION for a in restored)
    d = ready_core()
    reflect(d, 'scope', FakeReflection('concrete_evidence'), authorized=True)
    review_reflection(d, 'scope', "It's BPO, not PPO.")
    answer(d, 'scope', 'text', 'I always check logs.')
    answer(d, 'scope', 'skip')
    sources = confirmed_answers(d, 'scope')
    repo.confirm_company_interview(**dict(kw, company='New Company'), answers=sources, experience_id='new')
    new = repo.list_company_answers('c', 'new')
    assert {a.source_kind for a in new} == {'FIXED_QUESTION', 'REVIEW_CORRECTION', 'ADAPTIVE_QUESTION', 'FINAL_OPEN'}
    assert next(a for a in new if a.source_kind == 'REVIEW_CORRECTION').confirmed_text == "It's BPO, not PPO."
    assert len(new) == 11 and all(a.interview_version == VERSION for a in new)
    assert not repo.list_company_answers('foreign', 'new')
    from services.ai.candidate_profile_prompt_builder import build_candidate_profile_prompt
    from models.candidate_onboarding import CandidateOnboarding
    prompt = build_candidate_profile_prompt(CandidateOnboarding('c'), repo.list_work_experiences('c'))
    assert 'REVIEW_CORRECTION' in prompt and 'ADAPTIVE_QUESTION' in prompt and 'FINAL_OPEN' in prompt
    assert 'Occasional SQL use, not established expertise.' not in prompt  # Derived only.
    assert 'audio' not in json.dumps([asdict(a) for a in new])


def test_in_progress_v1_session_is_not_reinterpreted_or_discarded():
    d = draft()
    d['version'] = V1_VERSION
    answer(d, 'scope', 'text', 'Original V1 memory')
    d['answers'][0].pop('kind')  # Actual V1 session shape.
    for _ in range(6):
        answer(d, 'scope', 'skip')
    d.pop('after_processing')
    process(d, 'scope', Provider(), CONFIG, authorized=True)
    records = confirmed_answers(d, 'scope')
    assert len(records) == 7 and records[0].confirmed_text == 'Original V1 memory'
    assert all(r.interview_version == V1_VERSION for r in records)
    assert records[-1].question_text == V1_QUESTIONS[-1]
