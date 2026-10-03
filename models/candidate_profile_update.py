"""One confirmed source event, with authority supplied by the trusted caller."""
from dataclasses import dataclass

from models.source_reference import RegisteredSourceRef, SourceRefClass


@dataclass(frozen=True)
class CandidateProfileSourceSync:
    """Trusted caller attestation of the complete raw state incorporated by this update.

    The caller must establish that the base plus this event covers that state;
    merely hashing current raw data is not sufficient when other changes are pending.
    This is never interpreter output and contains no raw history.
    """
    candidate_id: str
    update_id: str
    raw_source_signature: str

    def __post_init__(self):
        if any(not isinstance(value, str) or not value.strip() for value in (
            self.candidate_id, self.update_id, self.raw_source_signature
        )):
            raise ValueError("Source synchronization identity and signature are required.")


@dataclass(frozen=True)
class CandidateProfileUpdateInput:
    update_id: str
    candidate_id: str
    update_type: str
    description: str
    source: RegisteredSourceRef
    created_at: str = ""

    def __post_init__(self):
        for name in ("update_id", "candidate_id", "update_type", "description"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Candidate update identity, type and description are required.")
            object.__setattr__(self, name, value.strip())
        if (self.source.ref != f"career_update:{self.update_id}"
                or self.source.owner_id != self.candidate_id
                or self.source.source_class not in {
                    SourceRefClass.CANDIDATE_EVIDENCE, SourceRefClass.CAREER_MEMORY_SOURCE}
                or self.source.confirmed_absence_for):
            raise ValueError("Invalid candidate update provenance.")
