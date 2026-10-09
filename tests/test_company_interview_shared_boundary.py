import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from models.company_interview import V1_VERSION, V2_VERSION, V3_VERSION, V4_VERSION, V3_QUESTIONS, V4_QUESTIONS
from services import company_interview as service


def draft_for(version):
    if version == V4_VERSION:
        return service.start_v4_interview("scope", "candidate", "Company", "Role", "2020-01", None)
    draft = service.start_v3_interview("scope", "candidate", "Company", "2020-01", None)
    draft["version"] = version
    return draft


@pytest.mark.parametrize("version", [V1_VERSION, V2_VERSION])
@pytest.mark.parametrize("operation", ["persist", "transcribe", "confirm_voice", "correction"])
def test_legacy_versions_cannot_enter_shared_path(version, operation, monkeypatch):
    draft = draft_for(version)
    repo, provider, duration = Mock(), Mock(), Mock(return_value=1)
    monkeypatch.setattr(service, "audio_duration", duration)
    config = SimpleNamespace(transcription_enabled=True, model="fake")
    if operation == "persist":
        draft["stage"] = "memory"
    elif operation == "confirm_voice":
        draft["stage"] = "voice_review"
        draft["pending_voice"] = dict(question_id="q1", question_text=V3_QUESTIONS[0],
                                      source_kind="FIXED_QUESTION", transcript="Source")
    elif operation == "correction":
        draft["stage"] = "review"
    before = copy.deepcopy(draft)
    with pytest.raises(ValueError):
        if operation == "persist":
            service._persist(draft, "scope", repo, mode="text", text="Source")
        elif operation == "transcribe":
            service.transcribe_voice(draft, "scope", b"audio", provider, config, authorized=True)
        elif operation == "confirm_voice":
            service.confirm_voice_transcript(draft, "scope", repo, "Source")
        else:
            service.save_correction(draft, "scope", repo, "Correction")
    assert draft == before
    assert repo.mock_calls == []
    assert provider.mock_calls == []
    duration.assert_not_called()


@pytest.mark.parametrize("version,questions", [(V3_VERSION, V3_QUESTIONS), (V4_VERSION, V4_QUESTIONS)])
def test_shared_text_voice_and_correction_keep_exact_version(version, questions, monkeypatch):
    draft = draft_for(version)
    repo = Mock()
    # Shared mechanics must dispatch directly, not through the legacy router.
    monkeypatch.setattr(service, "current_question", Mock(side_effect=AssertionError("legacy router")))
    text = service.confirm_text(draft, "scope", repo, "Text source")
    assert (text.question_id, text.question_text) == ("q1", questions[0])
    assert text.interview_version == text.question_version == version
    monkeypatch.setattr(service, "audio_duration", lambda _: 1)
    provider = Mock()
    provider.transcribe.return_value = SimpleNamespace(status="succeeded", transcript_text="Voice source")
    service.transcribe_voice(draft, "scope", b"audio", provider,
        SimpleNamespace(transcription_enabled=True, model="fake"), authorized=True)
    assert repo.save_company_answer.call_count == 1
    voice = service.confirm_voice_transcript(draft, "scope", repo, "Edited voice source")
    assert (voice.question_id, voice.question_text) == ("q2", questions[1])
    assert voice.interview_version == voice.question_version == version
    assert voice.answer_mode == "voice"
    for _ in questions[2:]:
        service.confirm_text(draft, "scope", repo, "Remaining source")
    assert draft["stage"] == "reflection_pending"
    # Coverage is tested separately; exercise correction at its review boundary.
    draft["stage"] = "review"
    correction = service.save_correction(draft, "scope", repo, "Correction")
    assert correction.interview_version == correction.question_version == version
    assert correction.source_kind == "REVIEW_CORRECTION"
