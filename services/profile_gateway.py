"""The terminal Profile operation exposed to Onboarding."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from models.candidate import Candidate
    from services.candidate_profile_generation_service import CandidateProfileGenerationService


class ProfileGateway(Protocol):
    def create_initial_profile(self, *, candidate_id: str, candidate_name: str) -> Candidate:
        ...


class CandidateProfileGateway:
    def __init__(self, generation_service: CandidateProfileGenerationService) -> None:
        self._generation_service = generation_service

    def create_initial_profile(self, *, candidate_id: str, candidate_name: str) -> Candidate:
        return self._generation_service.generate(
            candidate_id=candidate_id, candidate_name=candidate_name,
        )
