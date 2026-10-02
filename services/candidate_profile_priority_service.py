"""Profile priority operations over transitional Candidate storage."""
from copy import deepcopy

from models.candidate_priority import CandidatePriority
from services.candidate_repository import CandidateRepository


class CandidateProfilePriorityNotFoundError(ValueError):
    """The candidate required for priority operations does not exist."""


class CandidateProfilePriorityService:
    def __init__(self, repository: CandidateRepository) -> None:
        self._repository = repository

    def _load(self, candidate_id):
        candidate = self._repository.get(candidate_id)
        if candidate is None:
            raise CandidateProfilePriorityNotFoundError("Candidate profile was not found.")
        return deepcopy(candidate)

    @staticmethod
    def _priority(text: str, direction: str, active: bool) -> CandidatePriority:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Priority cannot be empty.")
        if direction not in ("positive", "negative"):
            raise ValueError("Unsupported priority direction.")
        if not isinstance(active, bool):
            raise ValueError("Priority active state must be boolean.")
        return CandidatePriority(text=text.strip(), direction=direction, active=active)

    @staticmethod
    def _check_index(priorities, index: int) -> None:
        if type(index) is not int or not 0 <= index < len(priorities):
            raise IndexError("Priority was not found.")

    def list(self, candidate_id: str) -> tuple[CandidatePriority, ...]:
        """Return ordered, detached priorities; missing candidate raises explicitly."""
        return tuple(self._load(candidate_id).priorities)

    def add(self, candidate_id: str, text: str, direction: str = "positive",
            active: bool = True) -> CandidatePriority:
        candidate = self._load(candidate_id)
        priority = self._priority(text, direction, active)
        candidate.priorities.append(priority)
        self._repository.save(candidate)
        return deepcopy(priority)

    def update(self, candidate_id: str, index: int, *, text: str,
               direction: str, active: bool) -> CandidatePriority:
        candidate = self._load(candidate_id)
        self._check_index(candidate.priorities, index)
        priority = self._priority(text, direction, active)
        candidate.priorities[index] = priority
        self._repository.save(candidate)
        return deepcopy(priority)

    def remove(self, candidate_id: str, index: int) -> CandidatePriority:
        """Remove and return only the priority at the supplied zero-based index."""
        candidate = self._load(candidate_id)
        self._check_index(candidate.priorities, index)
        priority = candidate.priorities.pop(index)
        self._repository.save(candidate)
        return deepcopy(priority)
