"""Candidate-authored education and certification source records."""
from dataclasses import dataclass


def _nonblank(*values):
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("Source fields must be nonblank strings.")


@dataclass(frozen=True)
class OnboardingEducationRecord:
    id: str
    candidate_id: str
    institution: str
    qualification: str
    field: str

    def __post_init__(self):
        _nonblank(self.id, self.candidate_id, self.institution, self.qualification, self.field)


@dataclass(frozen=True)
class OnboardingCertificationRecord:
    id: str
    candidate_id: str
    name: str
    issuer: str
    year_obtained: int

    def __post_init__(self):
        _nonblank(self.id, self.candidate_id, self.name, self.issuer)
        if type(self.year_obtained) is not int or not 1 <= self.year_obtained <= 9999:
            raise ValueError("year_obtained must be an integer year from 1 to 9999.")
