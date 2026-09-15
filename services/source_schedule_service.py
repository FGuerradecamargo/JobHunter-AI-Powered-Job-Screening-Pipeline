from dataclasses import dataclass, replace
from datetime import timedelta

import requests

from models.company import CompanyJobSource
from services.database import get_connection
from services.daily_ingestion_service import DailyIngestionService
from services.employer_provider_factories import employer_provider_factories
from services.employer_provider_registry import build_employer_provider_configs
from services.job_sources.board_http import BoardError
from services.job_sources.provider import default_providers
from services.source_run_repository import SourceRunRepository, utc_now, timestamp


@dataclass(frozen=True)
class SchedulePolicy:
    global_hours: int = 24
    employer_hours: int = 6
    failure_minutes: int = 30
    rate_limit_minutes: int = 120
    setup_minutes: int = 360
    degraded_minutes: int = 60

    def delay(self, vendor, status, error):
        if status == "success":
            return timedelta(hours=self.employer_hours if vendor in {"lever", "ashby"} else self.global_hours)
        minutes = (self.rate_limit_minutes if error == "rate_limited" else
                   self.setup_minutes if error in {"provider_setup_failed", "response_shape"} else
                   self.degraded_minutes if status == "partial" else self.failure_minutes)
        return timedelta(minutes=minutes)


def scheduled_sources():
    # Registry rows only: twenty subscribers still produce one shared board run.
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM company_job_sources ORDER BY id").fetchall()
    sources = [CompanyJobSource(**{**dict(row), "enabled": bool(row["enabled"])}) for row in rows]
    return default_providers(), sources


def error_category(error):
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return "transport_failure"
    if isinstance(error, requests.HTTPError) and getattr(error.response, "status_code", None) == 429:
        return "rate_limited"
    code = error.code if isinstance(error, BoardError) else ""
    if code in {"rate_limited", "http_retry_exhausted"}:
        return "rate_limited"
    if code.startswith("transport"):
        return "transport_failure"
    if code in {"response_shape", "invalid_json", "content_type", "pagination_stalled",
                "pagination_limit", "board_too_large", "response_too_large"}:
        return "response_shape"
    return "query_failed"


class SourceScheduleService:
    def __init__(self, repository=None, policy=None, clock=utc_now, factories=None):
        self.repository = repository or SourceRunRepository()
        self.policy = policy or SchedulePolicy()
        if any(value <= 0 for value in vars(self.policy).values()):
            raise ValueError("Scheduler delays must be positive.")
        self.clock = clock
        self.factories = factories if factories is not None else employer_provider_factories()

    def run(self, globals=None, employers=None, day_index=None):
        if globals is None or employers is None:
            default_globals, default_employers = scheduled_sources()
            globals = default_globals if globals is None else globals
            employers = default_employers if employers is None else employers
        employers = list(employers)
        configs = list(globals) + list(build_employer_provider_configs(employers, self.factories))
        rows = {f"{s.source_type}:{s.id}": s for s in employers}
        output = [{"source_identity": f"{s.source_type}:{s.id}", "status": "disabled", "attempted": False}
                  for s in employers if not s.enabled and s.source_type in self.factories]
        seen = set()
        for config in configs:
            identity = config.source_type
            if identity in seen:
                continue
            seen.add(identity)
            row = rows.get(identity)
            vendor = row.source_type if row else identity
            if not config.enabled or (row and not row.enabled):
                output.append({"source_identity": identity, "status": "disabled", "attempted": False})
                continue
            started = self.clock()
            run_id, claim = self.repository.acquire(identity, vendor, row.id if row else None, started)
            if run_id is None:
                output.append({"source_identity": identity, "status": claim, "attempted": False})
                continue
            metadata = {"error": None, "skipped": 0, "queries": 0}
            owner = self

            class ObservedSource:
                source_type = identity

                def __init__(self, source):
                    if source.source_type != identity:
                        raise ValueError("Provider identity mismatch.")
                    self.source = source

                def search(self, **kwargs):
                    if not owner.repository.renew(identity, run_id, owner.clock()):
                        raise BoardError("lease_lost")
                    try:
                        jobs = self.source.search(**kwargs)
                    except Exception as error:
                        metadata["error"] = error_category(error)
                        raise
                    if not owner.repository.renew(identity, run_id, owner.clock()):
                        metadata["error"] = "lease_lost"
                        raise BoardError("lease_lost")
                    metadata["queries"] += 1
                    metadata["skipped"] += getattr(self.source, "skipped_records", 0)
                    class FencedJobs(list):
                        def __iter__(self):
                            for job in super().__iter__():
                                if not owner.repository.renew(identity, run_id, owner.clock()):
                                    metadata["error"] = "lease_lost"
                                    raise BoardError("lease_lost")
                                yield job
                    return FencedJobs(jobs)

            observed = replace(config, factory=lambda: ObservedSource(config.factory()))
            # Existing ingestion keeps ownership of normalization and persistence.
            result = DailyIngestionService(providers=(observed,)).run(
                started.toordinal() if day_index is None else day_index,
            ).providers[identity]
            if result.error_code != "provider_setup_failed" and metadata["error"]:
                result.error_code = metadata["error"]
            if result.status == "success" and metadata["skipped"]:
                result.status, result.error_code = "partial", "degraded_records"
            complete = bool(row and result.status == "success" and metadata["queries"] == 1)
            ended = self.clock()
            next_at = ended + self.policy.delay(vendor, result.status, result.error_code)
            finalized = self.repository.finish(identity, run_id, ended, result, complete, next_at)
            output.append({"source_identity": identity, "attempted": True, "claimed": True,
                "status": result.status if finalized else "expired", "coverage_complete": complete if finalized else False,
                "jobs_fetched": result.fetched, "jobs_created": result.created,
                "jobs_updated": result.updated, "jobs_unchanged": result.unchanged,
                "failed_queries": result.failed_queries, "error_code": result.error_code if finalized else "lease_lost",
                "duration_seconds": result.duration_seconds, "next_eligible_at": timestamp(next_at) if finalized else None})
        return output
