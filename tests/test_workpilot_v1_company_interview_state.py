from types import SimpleNamespace

from models.company_interview import V3_QUESTIONS as QUESTIONS
from services.company_interview import (
    confirm_text,
    confirm_voice_transcript,
    current_question,
    _resume_v3_interview as resume_interview,
    set_adaptive_dimensions,
    start_v3_interview as start_interview,
    transcribe_voice,
)


class Repo:
    def __init__(self):
        self.saved = []

    def save_company_answer(self, **kwargs):
        self.saved.append(kwargs["answer"])


class Provider:
    def transcribe(self, audio, metadata, allow_external_transcription=False):
        assert allow_external_transcription is True
        return SimpleNamespace(
            status="succeeded",
            transcript_text="Confirmed transcript",
        )


class Config:
    transcription_enabled = True
    model = "fake"


def test_text_answer_is_persisted_before_next_question():
    repo = Repo()
    draft = start_interview(
        "scope", "c", "Company", "2020-01", None
    )
    assert current_question(draft)[0] == "q1"

    confirm_text(
        draft,
        "scope",
        repo,
        "Concrete answer",
    )

    assert len(repo.saved) == 1
    assert repo.saved[0].confirmed_text == "Concrete answer"
    assert current_question(draft)[0] == "q2"


def test_voice_transcript_is_not_persisted_until_user_confirms():
    repo = Repo()
    draft = start_interview(
        "scope", "c", "Company", "2020-01", None
    )

    # Minimal RIFF header accepted by the real duration helper is covered in
    # integration tests; bypass it here to focus on the persistence boundary.
    import services.company_interview as module
    original = module.audio_duration
    module.audio_duration = lambda value: 1.0
    try:
        transcribe_voice(
            draft,
            "scope",
            b"audio",
            Provider(),
            Config(),
            authorized=True,
        )
    finally:
        module.audio_duration = original

    assert repo.saved == []
    assert draft["stage"] == "voice_review"

    confirm_voice_transcript(
        draft,
        "scope",
        repo,
        "Confirmed transcript",
    )

    assert len(repo.saved) == 1
    assert repo.saved[0].answer_mode == "voice"
    assert current_question(draft)[0] == "q2"


def test_after_four_core_questions_reflection_is_next():
    repo = Repo()
    draft = start_interview(
        "scope", "c", "Company", "2020-01", None
    )
    for index in range(len(QUESTIONS)):
        confirm_text(
            draft,
            "scope",
            repo,
            f"Answer {index}",
        )
    assert draft["stage"] == "reflection_pending"


def test_adaptive_questions_are_capped_at_two():
    repo = Repo()
    draft = start_interview(
        "scope", "c", "Company", "2020-01", None
    )
    for index in range(len(QUESTIONS)):
        confirm_text(
            draft,
            "scope",
            repo,
            f"Answer {index}",
        )
    set_adaptive_dimensions(
        draft,
        "scope",
        [
            "core_work",
            "stakeholders",
            "tools_resources",
        ],
    )
    assert draft["adaptive_dimensions"] == [
        "core_work",
        "stakeholders",
    ]


def test_resume_uses_durable_source_answers():
    repo = Repo()
    draft = start_interview(
        "scope", "c", "Company", "2020-01", None
    )
    confirm_text(
        draft,
        "scope",
        repo,
        "First durable answer",
    )
    resumed = resume_interview(
        "scope",
        {
            "id": draft["id"],
            "candidate_id": "c",
            "company": "Company",
            "start_date": "2020-01",
            "end_date": None,
            "answers": repo.saved,
        },
    )
    assert resumed["core_index"] == 1
    assert current_question(resumed)[0] == "q2"
