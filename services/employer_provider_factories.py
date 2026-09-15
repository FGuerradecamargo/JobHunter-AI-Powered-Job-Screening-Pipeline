"""Trusted public-board builders for the existing Launch 1B registry bridge."""
from services.company_repository import CompanyRepository
from services.job_sources.ashby_source import AshbyJobSource
from services.job_sources.lever_source import LeverJobSource
from services.job_sources.board_http import BoardError


def employer_provider_factories(company_repository=None, http_factory=None) -> dict:
    repository = company_repository if company_repository is not None else CompanyRepository()

    def build(adapter, source):
        company = repository.get(source.company_id)
        if company is None:
            raise BoardError("company_unavailable")
        return adapter(source, company.canonical_name,
                       http=http_factory() if http_factory is not None else None)

    return {
        "lever": lambda source: build(LeverJobSource, source),
        "ashby": lambda source: build(AshbyJobSource, source),
    }
