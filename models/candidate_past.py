"""Past-domain values. Structure and source links only, never interpretation."""
from dataclasses import dataclass


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonblank string.")


def _date(value: str | None) -> None:
    # Preserve source precision (for example YYYY or YYYY-MM); do not infer dates.
    if value is not None:
        _text(value, "date")


def _collection(values: tuple, item_type: type) -> None:
    if not isinstance(values, tuple) or any(type(item) is not item_type for item in values):
        raise TypeError(f"Expected a tuple of {item_type.__name__} values.")
    if len({item.id for item in values}) != len(values):
        raise ValueError("Duplicate identities in collection.")


@dataclass(frozen=True)
class CandidateInput:
    """Original candidate wording; validation never rewrites the text."""

    id: str
    original_text: str

    def __post_init__(self) -> None:
        _text(self.id, "id")
        _text(self.original_text, "original_text")


@dataclass(frozen=True)
class ProfessionalFact:
    """An interpreted statement with a direct, parent-local original-input ref."""

    id: str
    statement: str
    candidate_input_id: str

    def __post_init__(self) -> None:
        for field in ("id", "statement", "candidate_input_id"):
            _text(getattr(self, field), field)
        if self.id == self.candidate_input_id:
            raise ValueError("A fact cannot reference itself.")


def _provenance(inputs: tuple[CandidateInput, ...], facts: tuple[ProfessionalFact, ...]) -> None:
    _collection(inputs, CandidateInput)
    _collection(facts, ProfessionalFact)
    input_ids = {item.id for item in inputs}
    fact_ids = {item.id for item in facts}
    if input_ids & fact_ids:
        raise ValueError("Input and fact identities must be distinct.")
    if any(fact.candidate_input_id not in input_ids for fact in facts):
        raise ValueError("Every fact must reference an original input in the same entity.")


@dataclass(frozen=True)
class Experience:
    id: str
    company: str
    role: str
    start_date: str | None = None
    end_date: str | None = None
    inputs: tuple[CandidateInput, ...] = ()
    facts: tuple[ProfessionalFact, ...] = ()

    def __post_init__(self) -> None:
        for field in ("id", "company", "role"):
            _text(getattr(self, field), field)
        _date(self.start_date)
        _date(self.end_date)
        _provenance(self.inputs, self.facts)


@dataclass(frozen=True)
class Education:
    id: str
    institution: str
    qualification: str
    field: str
    start_date: str | None = None
    end_date: str | None = None
    status: str | None = None
    inputs: tuple[CandidateInput, ...] = ()
    facts: tuple[ProfessionalFact, ...] = ()

    def __post_init__(self) -> None:
        for field in ("id", "institution", "qualification", "field"):
            _text(getattr(self, field), field)
        _date(self.start_date)
        _date(self.end_date)
        if self.status is not None:
            _text(self.status, "status")
        _provenance(self.inputs, self.facts)


@dataclass(frozen=True)
class Certification:
    """Formal credential only; status is supplied, never inferred from dates."""

    id: str
    name: str
    issuer: str
    issued_at: str | None = None
    expires_at: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        for field in ("id", "name", "issuer"):
            _text(getattr(self, field), field)
        _date(self.issued_at)
        _date(self.expires_at)
        if self.status is not None:
            _text(self.status, "status")


@dataclass(frozen=True)
class CandidatePast:
    experiences: tuple[Experience, ...] = ()
    education: tuple[Education, ...] = ()
    certifications: tuple[Certification, ...] = ()

    def __post_init__(self) -> None:
        _collection(self.experiences, Experience)
        _collection(self.education, Education)
        _collection(self.certifications, Certification)
