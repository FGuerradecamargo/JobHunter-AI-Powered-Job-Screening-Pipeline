import json
from pathlib import Path
from types import SimpleNamespace

from models.hiring_case import RequirementImportance
from models.profile_interpretation import (
    AIJobProfileSnapshot,
    InterpretationAuthority,
    InterpretedJobNeed,
    JobRequirementStatus,
)
from services.market_profile_refresh_service import (
    MarketProfileRefreshService,
)


def public_row(
    *,
    job_id="job-1",
    provider="jooble",
    external_id="provider-1",
    sub_category="Product Ops",
    url="https://jobs.example/1",
    remote=True,
):
    return {
        "observation_id": "obs-" + job_id,
        "job_id": job_id,
        "source_type": provider,
        "external_id": external_id,
        "payload_json": json.dumps(
            {
                "id": job_id,
                "title": "Product Operations Specialist",
                "company": "Example",
                "location": "Dublin",
                "url": url,
                "remote": remote,
                "salary": "EUR 50000",
            }
        ),
        "created_at": "2026-09-27T10:00:00+00:00",
        "updated_at": "2026-09-27T11:00:00+00:00",
        "last_seen_at": "2026-09-27T12:00:00+00:00",
        "category": "Product",
        "sub_category": sub_category,
        "search_query": "product operations",
    }


def job_profile(job_id="job-1", signature="sig-job-1"):
    return AIJobProfileSnapshot(
        job_id=job_id,
        profile_version=1,
        job_signature=signature,
        created_at="2026-09-27T12:00:00+00:00",
        needs=(
            InterpretedJobNeed(
                need_id="need-sql",
                label="SQL",
                importance=RequirementImportance.CORE,
                authority=InterpretationAuthority.EXPLICIT,
                hard_fact_refs=("fact-1",),
                requirement_status=JobRequirementStatus.REQUIRED,
            ),
        ),
        tools_as_means=("Jira",),
    )


class Sources:
    def __init__(self, rows):
        self.rows = rows

    def list_public_market_rows(self):
        return list(self.rows)

    def load_job_hard_facts(self, job_id):
        return SimpleNamespace(
            job_signature="sig-" + job_id
        )


class Profiles:
    def __init__(self, profiles):
        self.profiles = profiles

    def job_for_signature(
        self,
        job_id,
        signature,
        schema_version,
    ):
        profile = self.profiles.get(job_id)

        if (
            profile is not None
            and profile.job_signature == signature
        ):
            return profile

        return None


class Markets:
    def __init__(self):
        self.values = {}
        self.saved = []

    def current(self, segment):
        return self.values.get(segment)

    def save(self, profile):
        self.values[profile.segment] = profile
        self.saved.append(profile)


def test_global_market_refresh_uses_only_public_job_evidence():
    rows = [
        public_row(),
        public_row(
            job_id="job-2",
            provider="adzuna",
            external_id="provider-2",
            sub_category="Product Operations",
            url="https://jobs.example/2",
        ),
        public_row(
            job_id="private-job",
            provider="gmail",
            external_id="private-1",
            url="",
        ),
    ]

    markets = Markets()

    service = MarketProfileRefreshService(
        source_repository=Sources(rows),
        profile_repository=Profiles(
            {
                "job-1": job_profile(),
                # job-2 intentionally has no current JobProfile.
            }
        ),
        market_repository=markets,
        clock=lambda: "2026-09-27T13:00:00+00:00",
    )

    refreshed = service.refresh()

    assert len(refreshed) == 1

    market = refreshed[0]

    assert market.segment.role_family == "Product Operations"
    assert market.sample_size == 2

    sql = next(
        item
        for item in market.patterns
        if (
            item.dimension == "capability"
            and item.label == "SQL"
        )
    )

    jira = next(
        item
        for item in market.patterns
        if (
            item.dimension == "tool"
            and item.label == "Jira"
        )
    )

    assert sql.independent_jobs == 1
    assert jira.independent_jobs == 1

    assert all(
        "private-job" not in item.source_job_ids
        for item in market.patterns
    )


def test_stale_job_profile_does_not_become_market_capability():
    markets = Markets()

    service = MarketProfileRefreshService(
        source_repository=Sources(
            [public_row()]
        ),
        profile_repository=Profiles(
            {
                "job-1": job_profile(
                    signature="old-signature"
                )
            }
        ),
        market_repository=markets,
        clock=lambda: "2026-09-27T13:00:00+00:00",
    )

    market = service.refresh()[0]

    assert not any(
        item.dimension in {"capability", "tool"}
        for item in market.patterns
    )


def test_unchanged_global_evidence_does_not_write_new_snapshot():
    markets = Markets()

    service = MarketProfileRefreshService(
        source_repository=Sources(
            [public_row()]
        ),
        profile_repository=Profiles(
            {"job-1": job_profile()}
        ),
        market_repository=markets,
        clock=lambda: "2026-09-27T13:00:00+00:00",
    )

    first = service.refresh()
    second = service.refresh()

    assert first == second
    assert len(markets.saved) == 1


def test_market_repository_boundary_excludes_private_observations():
    source = Path(
        "services/job_source_repository.py"
    ).read_text(encoding="utf-8")

    assert "def list_public_market_rows" in source
    assert "WHERE o.user_id IS NULL" in source
    assert "job_discovery_signals" in source
    assert "j.archived_at IS NULL" in source


def test_improvements_refreshes_only_official_global_market():
    source = Path(
        "pages/4_Improvements.py"
    ).read_text(encoding="utf-8")

    assert "MarketProfileRefreshService().refresh()" in source
    assert "load_candidate_market_runtime" in source

    assert "market_position_service" not in source
    assert "career_intelligence_presenter" not in source
