"""Small first-party activation sink with strictly allowlisted metadata."""
from dataclasses import dataclass
import logging
from services.security_audit_repository import SecurityAuditRepository

EVENTS = frozenset(('onboarding_started', 'onboarding_step_viewed', 'first_answer_started',
    'first_answer_completed', 'transcription_started', 'transcription_succeeded',
    'transcription_failed', 'input_mode_selected', 'onboarding_step_completed',
    'onboarding_completed', 'candidate_profile_created', 'abandonment_step'))


@dataclass(frozen=True)
class OnboardingEvent:
    name: str
    step: int
    input_mode: str | None = None
    elapsed_seconds: int | None = None


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
