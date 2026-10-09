"""Recall state backed by confirmed source answers; interpretations are not sources."""
from uuid import uuid4
from models.company_interview import (QUESTIONS, VERSION, FINAL_QUESTION, CORRECTION_QUESTION,
    ADAPTIVE_QUESTIONS, ConfirmedCompanyAnswer, validate_answers, V1_VERSION, V1_QUESTIONS)
from services.ai.voice_transcription import audio_duration
from models.company_interview import V3_VERSION, V3_QUESTIONS, validate_single_answer
from models.company_interview import V4_VERSION, V4_QUESTIONS, V4_ADAPTIVE_QUESTIONS, validate_v4_partial_answers


def start_interview(scope, candidate_id, company, start_date, end_date, *, repository=None, version=VERSION, role=""):
    if version == V4_VERSION:
        draft = start_v4_interview(scope, candidate_id, company, role, start_date, end_date)
        if repository is not None:
            if repository.get_company_draft(candidate_id) is not None:
                return resume_interview(scope, candidate_id, repository)
            repository.begin_company_interview(candidate_id=candidate_id, company=company, role=role,
                start_date=start_date, end_date=end_date, experience_id=draft['id'], interview_version=V4_VERSION)
            draft['durable'] = True
        return draft
    if not scope or not candidate_id or not company.strip() or (end_date and end_date < start_date):
        raise ValueError('Check company and dates.')
    draft = dict(id=uuid4().hex, scope=scope, candidate_id=candidate_id, company=company.strip(),
        start_date=start_date, end_date=end_date, version=VERSION, answers=[], stage='memory', acknowledgement='')
    if version == V3_VERSION:
        draft = start_v3_interview(scope, candidate_id, company, start_date, end_date)
    if repository is not None:
        existing = repository.get_company_draft(candidate_id)
        if existing is not None:
            return resume_interview(scope, candidate_id, repository)
        repository.begin_company_interview(candidate_id=candidate_id, company=company, start_date=start_date,
            end_date=end_date, experience_id=draft['id'], interview_version=draft['version'])
        draft['durable'] = True
    return draft


def resume_interview(scope, candidate_id, repository):
    row = repository.get_company_draft(candidate_id)
    if row is None:
        return None
    if row['onboarding_interview_version'] == V4_VERSION:
        return _resume_v4_interview(scope, row)
    if row['onboarding_interview_version'] == V3_VERSION:
        return _resume_v3_interview(scope, row)
    saved = row['answers']
    questions = V1_QUESTIONS if row['onboarding_interview_version'] == V1_VERSION else (
        V3_QUESTIONS if row['onboarding_interview_version'] == V3_VERSION else QUESTIONS)
    by_id = {a.question_id: a for a in saved}
    ordered = [by_id[f'q{i+1}'] for i in range(len(questions)) if f'q{i+1}' in by_id]
    ordered += [a for a in saved if a.question_id not in {f'q{i+1}' for i in range(len(questions))}]
    complete = all(f'q{i+1}' in by_id for i in range(len(questions)))
    stage = ('review' if row['onboarding_interview_version'] in (V1_VERSION, V3_VERSION) or 'final' in by_id
             else 'final') if complete else 'memory'
    return dict(id=row['id'], candidate_id=candidate_id, scope=scope, company=row['company'],
        start_date=row['start_date'], end_date=row['end_date'], version=row['onboarding_interview_version'],
        durable=True, stage=stage, acknowledgement='', answers=[dict(question_id=a.question_id,
            question_text=a.question_text, kind=a.source_kind, version=a.interview_version,
            mode=a.answer_mode, text=a.confirmed_text, status='ready', audio=None) for a in ordered])


def current_question(draft):
    if draft['version'] == V4_VERSION:
        return current_v4_question(draft)
    if draft['version'] == V3_VERSION:
        return current_v3_question(draft)
    if draft['stage'] == 'memory':
        n = next(i for i in range(8) if f'q{i+1}' not in {a['question_id'] for a in draft['answers']})
        questions = V1_QUESTIONS if draft['version'] == V1_VERSION else QUESTIONS
        return f'q{n + 1}', questions[n], 'FIXED_QUESTION'
    if draft['stage'] == 'adaptive':
        dimension = draft['adaptive_dimension']
        return 'adaptive_' + dimension, ADAPTIVE_QUESTIONS[dimension], 'ADAPTIVE_QUESTION'
    if draft['stage'] == 'final':
        return 'final', FINAL_QUESTION, 'FINAL_OPEN'
    raise ValueError('Not a recall stage.')


def answer(draft, scope, mode, value='', *, repository=None):
    if draft['scope'] != scope or draft['version'] not in (VERSION, V1_VERSION):
        raise ValueError('Invalid interview state.')
    qid, text, kind = current_question(draft)
    if mode == 'voice':
        audio_duration(value)
    elif mode not in ('text', 'skip') or (mode == 'text' and (not value.strip() or len(value) > 20000)):
        raise ValueError('Provide an answer or skip.')
    if repository is not None and mode != 'voice':
        repository.save_company_answer(candidate_id=draft['candidate_id'], experience_id=draft['id'],
            answer=ConfirmedCompanyAnswer(qid, text, mode, value if mode == 'text' else '', mode == 'skip',
                draft['version'], draft['version'], kind))
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


def review_reflection(draft, scope, correction='', *, repository=None):
    if draft['scope'] != scope or draft['stage'] not in ('reflection_review', 'reflection_failed'):
        raise ValueError('Invalid review state.')
    if not isinstance(correction, str) or len(correction) > 20000:
        raise ValueError('Invalid correction.')
    if correction.strip():
        if repository is not None:
            repository.save_company_answer(candidate_id=draft['candidate_id'], experience_id=draft['id'],
                answer=ConfirmedCompanyAnswer('correction', CORRECTION_QUESTION, 'text', correction.strip(), False,
                    draft['version'], draft['version'], 'REVIEW_CORRECTION'))
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


def start_v3_interview(
    scope,
    candidate_id,
    company,
    start_date,
    end_date,
    *,
    experience_id=None,
):
    if (
        not scope
        or not candidate_id
        or not company.strip()
        or (end_date and end_date < start_date)
    ):
        raise ValueError("Check company and dates.")
    return {
        "id": experience_id or uuid4().hex,
        "scope": scope,
        "candidate_id": candidate_id,
        "company": company.strip(),
        "start_date": start_date,
        "end_date": end_date,
        "version": V3_VERSION,
        "answers": [],
        "core_index": 0,
        "adaptive_dimensions": [],
        "adaptive_index": 0,
        "stage": "question",
        "pending_voice": None,
        "reflection": None,
        "typing": False,
    }


def _resume_v3_interview(scope, record):
    draft = start_v3_interview(
        scope,
        record["candidate_id"],
        record["company"],
        record["start_date"],
        record["end_date"],
        experience_id=record["id"],
    )
    answers = list(record.get("answers") or [])
    draft["answers"] = answers
    core = [
        item
        for item in answers
        if item.source_kind == "FIXED_QUESTION"
    ]
    adaptive = [
        item
        for item in answers
        if item.source_kind == "ADAPTIVE_QUESTION"
    ]
    ids = {item.question_id for item in core}
    draft["core_index"] = next((i for i in range(len(V3_QUESTIONS)) if f'q{i+1}' not in ids), len(V3_QUESTIONS))
    draft["adaptive_index"] = len(adaptive)

    if len(core) < len(V3_QUESTIONS):
        draft["stage"] = "question"
    elif len(adaptive) >= 2:
        draft["stage"] = "review"
    else:
        # Reflection is derived and need not be durable. Re-evaluate coverage
        # from the durable source answers after a resumed session.
        draft["stage"] = "reflection_pending"
    return draft


def current_v3_question(draft):
    if draft["stage"] != "question":
        raise ValueError("Not in a question stage.")

    if draft["core_index"] < len(V3_QUESTIONS):
        index = draft["core_index"]
        return (
            f"q{index + 1}",
            V3_QUESTIONS[index],
            "FIXED_QUESTION",
        )

    dimensions = draft.get("adaptive_dimensions", [])
    index = draft.get("adaptive_index", 0)
    if index < len(dimensions):
        dimension = dimensions[index]
        return (
            "adaptive_" + dimension,
            ADAPTIVE_QUESTIONS[dimension],
            "ADAPTIVE_QUESTION",
        )

    raise ValueError("No question is pending.")


def _persist(
    draft,
    scope,
    repository,
    *,
    mode,
    text="",
):
    if draft["version"] not in (V3_VERSION, V4_VERSION) or draft["scope"] != scope:
        raise ValueError("Invalid interview state.")

    qid, question, kind = (
        current_v3_question(draft) if draft["version"] == V3_VERSION else current_v4_question(draft)
    )
    answer = ConfirmedCompanyAnswer(
        question_id=qid,
        question_text=question,
        answer_mode=mode,
        confirmed_text=text.strip() if mode != "skip" else "",
        skipped=(mode == "skip"),
        interview_version=draft["version"],
        question_version=draft["version"],
        source_kind=kind,
    )
    validate_single_answer(answer)

    # Durability boundary: save before moving the state machine forward.
    repository.save_company_answer(
        candidate_id=draft["candidate_id"],
        experience_id=draft["id"],
        answer=answer,
    )
    draft["answers"].append(answer)

    if draft["version"] == V4_VERSION:
        _advance_v4(draft)
        draft["typing"] = False
        return answer

    if kind == "FIXED_QUESTION":
        ids = {item.question_id for item in draft["answers"]}
        draft["core_index"] = next((i for i in range(len(V3_QUESTIONS)) if f'q{i+1}' not in ids), len(V3_QUESTIONS))
        draft["stage"] = (
            "question"
            if draft["core_index"] < len(V3_QUESTIONS)
            else "reflection_pending"
        )
    else:
        draft["adaptive_index"] += 1
        draft["stage"] = (
            "question"
            if draft["adaptive_index"]
            < len(draft["adaptive_dimensions"])
            else "review"
        )
    draft["typing"] = False
    return answer


def confirm_text(draft, scope, repository, text):
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError("Provide an answer or skip.")
    return _persist(
        draft,
        scope,
        repository,
        mode="text",
        text=text,
    )


def skip_question(draft, scope, repository):
    return _persist(
        draft,
        scope,
        repository,
        mode="skip",
    )


def transcribe_voice(
    draft,
    scope,
    audio,
    provider,
    config,
    *,
    authorized=False,
):
    if (
        draft["version"] not in (V3_VERSION, V4_VERSION)
        or draft["scope"] != scope
        or draft["stage"] != "question"
        or authorized is not True
    ):
        raise ValueError(
            "Voice transcription requires explicit confirmation."
        )

    qid, question, kind = (
        current_v3_question(draft) if draft["version"] == V3_VERSION else current_v4_question(draft)
    )
    audio_duration(audio)

    if not config.transcription_enabled or not config.model:
        raise ValueError("Voice transcription is unavailable.")

    result = provider.transcribe(
        audio,
        {"question_id": qid},
        allow_external_transcription=True,
    )
    transcript = (
        result.transcript_text
        if result.status == "succeeded"
        else ""
    )
    if (
        not isinstance(transcript, str)
        or not transcript.strip()
        or len(transcript) > 20000
    ):
        raise ValueError("Recording could not be transcribed.")

    # Audio is not retained after transcription. The transcript is still
    # pending and is not evidence until the user accepts it.
    draft["pending_voice"] = {
        "question_id": qid,
        "question_text": question,
        "source_kind": kind,
        "transcript": transcript.strip(),
    }
    draft["stage"] = "voice_review"


def confirm_voice_transcript(
    draft,
    scope,
    repository,
    text,
):
    if (
        draft["version"] not in (V3_VERSION, V4_VERSION)
        or draft["scope"] != scope
        or draft["stage"] != "voice_review"
        or not draft.get("pending_voice")
    ):
        raise ValueError("No voice transcript is awaiting confirmation.")
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError("Confirm or edit the transcript.")

    pending = draft["pending_voice"]
    # Restore the question stage solely for the shared persistence boundary.
    draft["stage"] = "question"
    qid, question, kind = (
        current_v3_question(draft) if draft["version"] == V3_VERSION else current_v4_question(draft)
    )
    if (
        qid != pending["question_id"]
        or question != pending["question_text"]
        or kind != pending["source_kind"]
    ):
        draft["stage"] = "voice_review"
        raise ValueError("Voice transcript no longer matches the question.")

    try:
        answer = _persist(draft, scope, repository, mode="voice", text=text)
    except Exception:
        draft["stage"] = "voice_review"
        raise
    draft["pending_voice"] = None
    return answer


def discard_voice(draft, scope):
    if draft["scope"] != scope or draft["stage"] != "voice_review":
        raise ValueError("No voice transcript is awaiting review.")
    draft["pending_voice"] = None
    draft["stage"] = "question"


def set_adaptive_dimensions(draft, scope, dimensions):
    if draft["version"] == V4_VERSION:
        raise ValueError("V4 requires one coverage decision at a time.")
    if draft["scope"] != scope or draft["stage"] != "reflection_pending":
        raise ValueError("Adaptive questions are not expected now.")

    already_answered = {
        item.question_id.removeprefix("adaptive_")
        for item in draft["answers"]
        if item.source_kind == "ADAPTIVE_QUESTION"
    }
    clean = []
    for dimension in dimensions or []:
        if (
            dimension in ADAPTIVE_QUESTIONS
            and dimension not in already_answered
            and dimension not in clean
        ):
            clean.append(dimension)

    # V1 contract: zero to two adaptive questions total.
    remaining = max(0, 2 - len(already_answered))
    draft["adaptive_dimensions"] = clean[:remaining]
    draft["adaptive_index"] = 0
    draft["stage"] = (
        "question"
        if draft["adaptive_dimensions"]
        else "review"
    )


def save_correction(draft, scope, repository, text):
    if (draft["version"] not in (V3_VERSION, V4_VERSION)
            or draft["scope"] != scope or draft["stage"] != "review"):
        raise ValueError("Review is required.")
    if not isinstance(text, str) or len(text) > 20000:
        raise ValueError("Invalid correction.")
    if not text.strip():
        return None

    answer = ConfirmedCompanyAnswer(
        "correction",
        CORRECTION_QUESTION,
        "text",
        text.strip(),
        False,
        draft["version"],
        draft["version"],
        "REVIEW_CORRECTION",
    )
    validate_single_answer(answer)
    repository.save_company_answer(
        candidate_id=draft["candidate_id"],
        experience_id=draft["id"],
        answer=answer,
        expected_answer=next((item for item in draft['answers'] if item.question_id == 'correction'), None),
    )
    # Replace a prior correction in the in-session view.
    draft["answers"] = [
        item
        for item in draft["answers"]
        if item.question_id != "correction"
    ]
    draft["answers"].append(answer)
    return answer


def finalize(draft, scope, repository):
    if draft["scope"] != scope or draft["stage"] != "review":
        raise ValueError("Review is required.")
    repository.finalize_company_interview(
        candidate_id=draft["candidate_id"],
        experience_id=draft["id"],
        expected_answers=draft['answers'],
    )
    draft["stage"] = "complete"


def start_v4_interview(scope, candidate_id, company, role, start_date, end_date, *, experience_id=None):
    if (any(not isinstance(value, str) or not value.strip()
            for value in (scope, candidate_id, company, role, start_date))
            or (end_date is not None and (not isinstance(end_date, str) or end_date < start_date))):
        raise ValueError("V4 requires company, role and valid dates.")
    return dict(id=experience_id or uuid4().hex, scope=scope, candidate_id=candidate_id,
        company=company.strip(), role=role, start_date=start_date, end_date=end_date,
        version=V4_VERSION, answers=[], stage="question", pending_voice=None,
        adaptive_dimension=None, reflection=None, typing=False)


def _advance_v4(draft):
    validate_v4_partial_answers(draft["answers"])
    ids = {a.question_id for a in draft["answers"]}
    draft["adaptive_dimension"] = None
    draft["reflection"] = None
    if not {"q1", "q2", "q3"}.issubset(ids):
        draft["stage"] = "question"
    elif sum(qid.startswith("adaptive_") for qid in ids) >= 2:
        draft["stage"] = "review"
    else:
        draft["stage"] = "reflection_pending"


def _resume_v4_interview(scope, record):
    draft = start_v4_interview(scope, record["candidate_id"], record["company"], record["role"],
        record["start_date"], record["end_date"], experience_id=record["id"])
    draft["answers"] = list(record["answers"])
    draft["durable"] = True
    _advance_v4(draft)
    return draft


def current_v4_question(draft):
    if draft["stage"] != "question":
        raise ValueError("Not in a question stage.")
    validate_v4_partial_answers(draft["answers"])
    ids = {a.question_id for a in draft["answers"]}
    for index, text in enumerate(V4_QUESTIONS, 1):
        if f"q{index}" not in ids:
            return f"q{index}", text, "FIXED_QUESTION"
    dimension = draft.get("adaptive_dimension")
    if (isinstance(dimension, str) and dimension in V4_ADAPTIVE_QUESTIONS
            and "adaptive_" + dimension not in ids
            and sum(qid.startswith("adaptive_") for qid in ids) < 2):
        return "adaptive_" + dimension, V4_ADAPTIVE_QUESTIONS[dimension], "ADAPTIVE_QUESTION"
    raise ValueError("No question is pending.")
