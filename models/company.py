from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Company:
    id: str
    canonical_name: str
    normalized_name: str
    domain: str | None
    careers_url: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CompanyJobSource:
    id: str
    company_id: str
    source_type: str
    source_key: str
    careers_url: str | None
    enabled: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MonitoredCompany:
    candidate_id: str
    company: Company
    active: bool
    created_at: str
    updated_at: str
