"""Small first-party activation sink with strictly allowlisted metadata."""
from dataclasses import dataclass
import logging
from services.security_audit_repository import SecurityAuditRepository

EVENTS = frozenset(('onboarding_started', 'onboarding_step_viewed', 'first_answer_started',
    'first_answer_completed', 'transcription_started', 'transcription_succeeded',
    'transcription_failed', 'input_mode_selected', 'onboarding_step_completed',
    'onboarding_completed', 'candidate_profile_created', 'abandonment_step',
    'company_interview_started', 'company_question_viewed', 'company_question_answered',
    'company_question_skipped', 'company_interview_completed', 'company_transcription_started',
    'company_transcription_completed', 'company_transcription_failed', 'company_review_started', 'company_confirmed',
    'company_reflection_started', 'company_reflection_completed', 'company_reflection_failed',
    'company_reflection_reviewed', 'company_adaptive_question_shown', 'company_adaptive_question_answered',
    'company_final_question_answered'))


@dataclass(frozen=True)
class OnboardingEvent:
    name: str
    step: int
    input_mode: str | None = None
    elapsed_seconds: int | None = None
    question_id: str | None = None


class OnboardingEventRepository:
    def __init__(self, authenticated_user_id, active_user_id, candidate_id, *, repository=None):
        self.actor, self.active, self.candidate = authenticated_user_id, active_user_id, candidate_id
        self.repository = repository or SecurityAuditRepository()

    def record(self, event):
        if event.name not in EVENTS or type(event.step) is not int or event.step not in (1, 2, 3, 4):
            raise ValueError('invalid_onboarding_event')
        if event.input_mode not in (None, 'voice', 'text') or (event.elapsed_seconds is not None and
                (type(event.elapsed_seconds) is not int or not 0 <= event.elapsed_seconds <= 604800)):
            raise ValueError('invalid_onboarding_event')
        metadata = dict(step=event.step)
        if event.question_id is not None:
            from models.company_interview import ADAPTIVE_QUESTIONS
            if event.question_id not in (*tuple(f'q{i}' for i in range(1, 9)), 'final',
                    *tuple('adaptive_' + d for d in ADAPTIVE_QUESTIONS)):
                raise ValueError('invalid_onboarding_event')
            metadata['question_id'] = event.question_id
        if event.input_mode is not None:
            metadata['input_mode'] = event.input_mode
        if event.elapsed_seconds is not None:
            metadata['elapsed_seconds'] = event.elapsed_seconds
        try:
            self.repository.record(event_type=event.name, outcome='success',
                authenticated_user_id=self.actor, active_user_id=self.active,
                target_type='candidate', target_id=self.candidate, metadata=metadata)
        except Exception:
            logging.getLogger(__name__).warning('onboarding_event_unavailable')
