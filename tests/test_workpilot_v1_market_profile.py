import pytest
from dataclasses import FrozenInstanceError, replace

from services.market_job_observation import global_market_job_identity, public_market_observation
from services.market_profile_repository import MarketProfileRepository

from models.market_profile import (
    MarketJobObservation,
    MarketSegment,
)
from services.market_profile_builder import (
    build_market_profile,
)


def observation(job_id, *, work_mode="", capabilities=(), source_refs=None):
    return MarketJobObservation(
        job_id=job_id,
        observed_at="2026-09-26T00:00:00+00:00",
        source_refs=source_refs or (f"public:{job_id}",),
        role_family="Operations",
        location="Ireland",
        seniority="Mid",
        domain="Technology",
        work_mode=work_mode,
        employment_type="Permanent",
        capabilities=capabilities,
        tools=(),
    )


def test_market_profile_has_no_candidate_identity():
    profile = build_market_profile(
        observations=[observation("job-1")],
        segment=MarketSegment(
            role_family="Operations",
            location="Ireland",
        ),
        created_at="2026-09-26T00:00:00+00:00",
    )
    assert not hasattr(profile, "candidate_id")
    assert profile.authority == "global_market_evidence"


def test_private_source_cannot_enter_global_market():
    with pytest.raises(ValueError, match="Private"):
        observation(
            "job-1",
            source_refs=("gmail:user-1:message-1",),
        )


def test_same_global_job_counts_once_across_multiple_observations():
    one = observation(
        "job-1",
        work_mode="Hybrid",
        source_refs=("public:linkedin:1",),
    )
    duplicate = observation(
        "job-1",
        work_mode="Hybrid",
        source_refs=("public:company:1",),
    )
    profile = build_market_profile(
        observations=[one, duplicate],
        segment=MarketSegment(
            role_family="Operations",
            location="Ireland",
        ),
        created_at="2026-09-26T00:00:00+00:00",
    )
    assert profile.sample_size == 1
    hybrid = next(
        item for item in profile.patterns
        if item.dimension == "work_mode"
    )
    assert hybrid.independent_jobs == 1
    assert hybrid.frequency == 1.0


def test_market_patterns_come_from_jobs_not_candidate_fit():
    profile = build_market_profile(
        observations=[
            observation(
                "job-1",
                capabilities=("SQL", "Reporting"),
            ),
            observation(
                "job-2",
                capabilities=("SQL",),
            ),
            observation(
                "job-3",
                capabilities=("Stakeholder management",),
            ),
        ],
        segment=MarketSegment(
            role_family="Operations",
            location="Ireland",
        ),
        created_at="2026-09-26T00:00:00+00:00",
    )
    sql = next(
        item for item in profile.patterns
        if item.dimension == "capability"
        and item.label == "SQL"
    )
    assert sql.independent_jobs == 2
    assert sql.sample_size == 3
    assert sql.frequency == 0.6667


def test_unchanged_sources_reuse_previous_profile():
    observations = [observation("job-1")]
    first = build_market_profile(
        observations=observations,
        segment=MarketSegment(role_family="Operations"),
        created_at="2026-09-26T00:00:00+00:00",
    )
    second = build_market_profile(
        observations=observations,
        segment=MarketSegment(role_family="Operations"),
        created_at="2026-09-27T00:00:00+00:00",
        previous=first,
    )
    assert second is first


def test_changed_market_creates_new_version():
    first = build_market_profile(
        observations=[observation("job-1")],
        segment=MarketSegment(role_family="Operations"),
        created_at="2026-09-26T00:00:00+00:00",
    )
    second = build_market_profile(
        observations=[
            observation("job-1"),
            observation("job-2"),
        ],
        segment=MarketSegment(role_family="Operations"),
        created_at="2026-09-27T00:00:00+00:00",
        previous=first,
    )
    assert second.profile_version == 2
    assert second.supersedes_version == 1


def build(rows, **kwargs):
    return build_market_profile(observations=rows, segment=MarketSegment(),
                                created_at="2026-09-27T00:00:00+00:00", **kwargs)


@pytest.mark.parametrize("source", ["gmail:x", "GMAIL:x", "manual:x", "user:x", "unknown:x", "import:x"])
def test_private_or_unclassified_provenance_rejected(source):
    with pytest.raises(ValueError):
        observation("j", source_refs=(source,))


def test_public_projection_rejects_private_owner_and_candidate_fields():
    args = dict(provider="jooble", source_id="1", observed_at="2026-09-26T00:00:00+00:00",
                identity={}, facts={})
    with pytest.raises(ValueError):
        public_market_observation(user_id="user-a", **args)
    with pytest.raises(ValueError):
        public_market_observation(user_id=None, **{**args, "facts": {"candidate_id": "a"}})
    assert public_market_observation(user_id=None, **args).source_refs == ("public:jooble:1",)


def test_exact_identity_tracking_and_namespace_boundaries():
    identity = global_market_job_identity
    assert identity(public_url="https://jobs.example/1?utm_source=a") == identity(public_url="https://jobs.example/1")
    assert identity(provider="lever", source_id="1") != identity(provider="ashby", source_id="1")
    assert identity(company_id="c", requisition_id="1", provider="lever") == identity(company_id="c", requisition_id="1", provider="ashby")
    with pytest.raises(ValueError):
        identity(company="same", title="same")
    assert identity(company="same", title="same", location="Dublin", context="team-a") != identity(company="same", title="same", location="Dublin", context="team-b")


def test_fuzzy_jobs_are_not_merged_and_unknown_compensation_stays_unknown():
    profile = build([observation("a"), observation("b")])
    assert profile.sample_size == 2
    assert profile.compensation_observed_count == 0
    assert "small_sample" in profile.uncertainties
    assert not any(p.dimension == "compensation" for p in profile.patterns)


def test_public_duplicates_order_independent_conflicts_unknown_and_sources_signed():
    a = observation("a", work_mode="Remote", source_refs=("public:lever:1",))
    b = observation("a", work_mode="Office", source_refs=("public:ashby:1",))
    profile = build([a, b])
    assert profile == build([b, a])
    assert profile.sample_size == 1
    assert not any(p.dimension == "work_mode" for p in profile.patterns)
    assert "conflicting_public_work_mode" in profile.uncertainties
    assert profile.source_signature != build([a]).source_signature
    assert profile.source_signature == build([a, b, a]).source_signature


def test_explicit_compensation_is_coverage_only():
    profile = build([replace(observation("a"), compensation="EUR 50000"), observation("b")])
    assert profile.compensation_observed_count == 1
    with pytest.raises(ValueError):
        replace(observation("b"), compensation_known=True)


def test_window_is_applied_and_invalid_window_rejected():
    args = dict(observations=[observation("a"), replace(observation("b"), observed_at="2026-09-01T00:00:00+00:00")],
                created_at="2026-09-27T00:00:00+00:00")
    profile = build_market_profile(**args, segment=MarketSegment(time_window="2026-09-20T00:00:00+00:00/2026-09-27T00:00:00+00:00"))
    assert profile.sample_size == 1
    with pytest.raises(ValueError):
        build_market_profile(**args, segment=MarketSegment(time_window="last week"))


def test_empty_and_immutable_global_profile():
    profile = build([])
    assert profile.sample_size == 0 and profile.patterns == ()
    assert "no_observations" in profile.uncertainties
    with pytest.raises(FrozenInstanceError):
        profile.sample_size = 100
    assert not hasattr(profile, "candidate_id")


def test_durable_history_reuse_conflict_and_roundtrip():
    repo = MarketProfileRepository()
    first = build([observation("a")])
    repo.save(first)
    repo.save(first)
    assert repo.current(first.segment) == first
    second = build([observation("a"), observation("b")], previous=first)
    repo.save(second)
    assert repo.version(first.segment, 1) == first
    assert repo.current(first.segment) == second
    assert build([observation("a"), observation("b")], previous=repo.current(first.segment)) == second
    with pytest.raises(ValueError, match="reload"):
        repo.save(build([observation("c")], previous=first))
    assert repo.current(first.segment) == second


def test_postgres_market_schema_is_server_only(monkeypatch):
    from services import database

    class Connection:
        def __init__(self):
            self.queries = []

        def execute(self, query):
            self.queries.append(query)

    connection = Connection()
    monkeypatch.setattr(database, "is_postgres", lambda: True)
    database.create_profile_interpretation_schema(connection)
    sql = "\n".join(connection.queries)
    assert "market_profile_snapshots ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON TABLE market_profile_snapshots FROM PUBLIC" in sql
