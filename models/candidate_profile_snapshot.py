"""CPV2 whole-candidate state, isolated from legacy profile interpretation."""
from dataclasses import dataclass

from models.candidate_past import CandidatePast
from models.candidate_present import CandidatePresent
from models.candidate_future import CandidateFuture
from models.candidate_priorities import CandidatePriorities


@dataclass(frozen=True)
class CandidateProfileSnapshot:
    """Materialized candidate at version T, with four independent branches.

    V1 originates from initial evidence; subsequent versions use the current
    snapshot plus new information. Generation, updates and current selection
    belong outside this value. Historical existence does not imply currentness.
    """

    candidate_id: str
    version: int
    past: CandidatePast
    present: CandidatePresent
    future: CandidateFuture
    priorities: CandidatePriorities

    def __post_init__(self) -> None:
        if type(self.candidate_id) is not str or not self.candidate_id.strip():
            raise ValueError("candidate_id must be a nonblank string.")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("version must be a positive integer.")
        for name, branch_type in (
            ("past", CandidatePast),
            ("present", CandidatePresent),
            ("future", CandidateFuture),
            ("priorities", CandidatePriorities),
        ):
            if type(getattr(self, name)) is not branch_type:
                raise TypeError(f"{name} must be a {branch_type.__name__}.")
