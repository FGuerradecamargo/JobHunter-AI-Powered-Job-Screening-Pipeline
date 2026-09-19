"""Session-only recall and deferred transcription. No persistence or semantic inference."""
from uuid import uuid4
from models.company_interview import (QUESTIONS, VERSION, FINAL_QUESTION, CORRECTION_QUESTION,
    ADAPTIVE_QUESTIONS, ConfirmedCompanyAnswer, validate_answers, V1_VERSION, V1_QUESTIONS)
from services.ai.voice_transcription import audio_duration


def start_interview(scope, candidate_id, company, start_date, end_date):
    if not scope or not candidate_id or not company.strip() or (end_date and end_date < start_date):
        raise ValueError('Check company and dates.')
    return dict(id=uuid4().hex, scope=scope, candidate_id=candidate_id, company=company.strip(),
        start_date=start_date, end_date=end_date, version=VERSION, answers=[], stage='memory', acknowledgement='')


def current_question(draft):
    if draft['stage'] == 'memory':
        n = len(draft['answers'])
        questions = V1_QUESTIONS if draft['version'] == V1_VERSION else QUESTIONS
        return f'q{n + 1}', questions[n], 'FIXED_QUESTION'
    if draft['stage'] == 'adaptive':
        dimension = draft['adaptive_dimension']
        return 'adaptive_' + dimension, ADAPTIVE_QUESTIONS[dimension], 'ADAPTIVE_QUESTION'
    if draft['stage'] == 'final':
        return 'final', FINAL_QUESTION, 'FINAL_OPEN'
    raise ValueError('Not a recall stage.')


def answer(draft, scope, mode, value=''):
    if draft['scope'] != scope or draft['version'] not in (VERSION, V1_VERSION):
        raise ValueError('Invalid interview state.')
    qid, text, kind = current_question(draft)
    if mode == 'voice':
        audio_duration(value)
    elif mode not in ('text', 'skip') or (mode == 'text' and (not value.strip() or len(value) > 20000)):
        raise ValueError('Provide an answer or skip.')
    draft['answers'].append(dict(question_id=qid, question_text=text, kind=kind,
        version=draft['version'], mode=mode, audio=value if mode == 'voice' else None,
        text=value if mode == 'text' else '', status='pending' if mode == 'voice' else 'ready'))
    if draft['version'] == V1_VERSION and len(draft['answers']) == 7:
        draft.update(stage='finish', after_processing='review')
    elif kind == 'ADAPTIVE_QUESTION':
        draft.update(stage='finish_extra' if mode == 'voice' else 'final', after_processing='final')
    elif kind == 'FINAL_OPEN':
        draft.update(stage='finish_extra' if mode == 'voice' else 'review', after_processing='review')
    elif len(draft['answers']) == 8:
        draft.update(stage='finish', after_processing='reflection_pending')


def process(draft, scope, provider, config, *, authorized=False):
    if draft['scope'] != scope or draft['stage'] not in ('finish', 'finish_extra', 'failed') or authorized is not True:
        raise ValueError('Processing requires explicit confirmation.')
    for item in draft['answers']:
        if item['mode'] != 'voice' or item['status'] == 'ready':
            continue
        item['status'] = 'failed'
        if not config.transcription_enabled or not config.model:
            continue
        try:
            result = provider.transcribe(item['audio'], {'question_id': item['question_id']},
                allow_external_transcription=True)
            if result.status == 'succeeded' and isinstance(result.transcript_text, str) and result.transcript_text.strip() and len(result.transcript_text) <= 20000:
                item.update(text=result.transcript_text, status='ready', audio=None)
        except Exception:
            pass  # Only a generic technical failure is exposed, never provider payloads.
    advance_after_processing(draft)


def advance_after_processing(draft):
    destination = 'review' if draft['version'] == V1_VERSION else draft['after_processing']
    draft['stage'] = 'failed' if any(a['status'] != 'ready' for a in draft['answers']) else destination


def review_reflection(draft, scope, correction=''):
    if draft['scope'] != scope or draft['stage'] not in ('reflection_review', 'reflection_failed'):
        raise ValueError('Invalid review state.')
    if not isinstance(correction, str) or len(correction) > 20000:
        raise ValueError('Invalid correction.')
    if correction.strip():
        draft['answers'].append(dict(question_id='correction', question_text=CORRECTION_QUESTION,
            kind='REVIEW_CORRECTION', version=VERSION, mode='text', text=correction.strip(), audio=None, status='ready'))
    dimension = (draft.get('reflection') or {}).get('material_missing_dimension')
    draft['adaptive_dimension'] = dimension
    draft['stage'] = 'adaptive' if dimension else 'final'
    draft['acknowledgement'] = 'Almost done.'


def confirmed_answers(draft, scope):
    if draft['scope'] != scope or draft['stage'] != 'review':
        raise ValueError('Review is required.')
    result = [ConfirmedCompanyAnswer(a['question_id'], a['question_text'], a['mode'],
        a['text'].strip() if a['mode'] != 'skip' else '', a['mode'] == 'skip',
        interview_version=draft['version'], question_version=draft['version'],
        source_kind=a.get('kind', 'FIXED_QUESTION')) for a in draft['answers']]
    validate_answers(result)
    return result
