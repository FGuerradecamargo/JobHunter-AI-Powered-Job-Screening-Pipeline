from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


COMPANY_PROFILE_SCHEMA_VERSION = "company-profile-v1"
PUBLIC_SOURCE_TYPES = frozenset({"company_website", "public_filing", "professional_news", "public_job_posting"})
CONTEXT_FIELDS = ("what_they_do", "products_services", "market_context", "size_context",
                  "public_culture_signals", "public_strategy_priorities", "recent_developments", "role_context")


def _clean(value: str) -> str:
    return " ".join(str(value or "").split())


def _refs(values) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                _clean(value)
                for value in values or ()
                if _clean(value)
            }
        )
    )


@dataclass(frozen=True)
class CompanyPublicSource:
    ref: str
    source_type: str
    title: str = ""
    published_at: str = ""
    summary: str = ""
    public: bool = True
    company_id: str = ""

    def __post_init__(self) -> None:
        for name in ("ref", "source_type", "company_id", "title", "summary", "published_at"):
            object.__setattr__(self, name, _clean(getattr(self, name)))
        if self.public is not True:
            raise ValueError(
                "CompanyProfile accepts public professional sources only."
            )
        if not _clean(self.ref) or not _clean(self.source_type):
            raise ValueError(
                "Company public source requires identity and type."
            )
        namespace = self.ref.casefold().split(":", 1)[0]
        if namespace not in {"web", "https"} or self.source_type not in PUBLIC_SOURCE_TYPES or not self.company_id:
            raise ValueError("Eligible public company provenance is required.")


@dataclass(frozen=True)
class CompanyClaim:
    field: str
    value: str
    source_ref: str
    attribution: str = "source_reported"

    def __post_init__(self):
        for name in ("field", "value", "source_ref"):
            object.__setattr__(self, name, _clean(getattr(self, name)))
        if self.field not in CONTEXT_FIELDS or not self.value or not self.source_ref:
            raise ValueError("Company claim requires professional context and provenance.")
        if self.attribution != "source_reported":
            raise ValueError("Company signals cannot be promoted to verified facts.")


@dataclass(frozen=True)
class CompanyProfileDraft:
    what_they_do: str = ""
    products_services: tuple[str, ...] = ()
    market_context: tuple[str, ...] = ()
    size_context: str = ""
    public_culture_signals: tuple[str, ...] = ()
    public_strategy_priorities: tuple[str, ...] = ()
    recent_developments: tuple[str, ...] = ()
    role_context: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    claims: tuple[CompanyClaim, ...] = ()


@dataclass(frozen=True)
class CompanyProfileSnapshot:
    company_id: str
    profile_version: int
    source_signature: str
    created_at: str
    source_refs: tuple[str, ...]
    what_they_do: str = ""
    products_services: tuple[str, ...] = ()
    market_context: tuple[str, ...] = ()
    size_context: str = ""
    public_culture_signals: tuple[str, ...] = ()
    public_strategy_priorities: tuple[str, ...] = ()
    recent_developments: tuple[str, ...] = ()
    role_context: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    supersedes_version: int | None = None
    schema_version: str = COMPANY_PROFILE_SCHEMA_VERSION
    authority: str = "public_company_context"
    claims: tuple[CompanyClaim, ...] = ()
    sources: tuple[CompanyPublicSource, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "company_id", _clean(self.company_id))
        object.__setattr__(self, "source_signature", _clean(self.source_signature))
        object.__setattr__(self, "source_refs", _refs(self.source_refs))
        if not self.company_id or self.profile_version < 1:
            raise ValueError(
                "Company profile identity and positive version are required."
            )
        if not self.source_signature or not _clean(self.created_at):
            raise ValueError(
                "Company profile signature and timestamp are required."
            )
        if self.supersedes_version != (self.profile_version - 1 if self.profile_version > 1 else None):
            raise ValueError("Company history predecessor is invalid.")
        if not self.source_refs:
            raise ValueError(
                "Company profile requires public source provenance."
            )
        if self.authority != "public_company_context":
            raise ValueError("Company profile authority is fixed.")
        if datetime.fromisoformat(self.created_at).tzinfo is None:
            raise ValueError("Company timestamp requires a timezone.")
        for name in (*CONTEXT_FIELDS, "uncertainties", "claims", "sources"):
            if name not in {"what_they_do", "size_context"}:
                object.__setattr__(self, name, tuple(getattr(self, name)))
        validate_grounding(self.company_id, self.sources, self)


def validate_grounding(company_id, sources, context):
    by_ref = {}
    for source in sources:
        if source.company_id != company_id:
            raise ValueError("Company source scope mismatch.")
        if source.ref in by_ref and by_ref[source.ref] != source:
            raise ValueError("Conflicting company source reference.")
        by_ref[source.ref] = source
    if not by_ref:
        raise ValueError("Public company sources are required.")
    if hasattr(context, "source_refs") and set(context.source_refs) != set(by_ref):
        raise ValueError("Company source references do not match evidence.")
    grounded = set()
    for claim in context.claims:
        source = by_ref.get(claim.source_ref)
        if source is None or claim.value not in source.summary:
            raise ValueError("Company claim is not grounded in its public source.")
        grounded.add((claim.field, claim.value))
    expected = set()
    for name in CONTEXT_FIELDS:
        values = getattr(context, name)
        values = (values,) if isinstance(values, str) else values
        expected.update((name, value) for value in values if value)
    if grounded != expected:
        raise ValueError("Every company context value requires an attributed source claim.")
