"""Bounded Launch 1E validation. Live collection requires explicit --live.

No candidate data, production DB, Gmail or AI dependencies are used. Database
work and scheduler repeats use a temporary SQLite database and replayed jobs.
"""
import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlsplit

import requests

from models.candidate_profile import CandidateProfile
from models.job_profile import JobProfile
from services.analyzers.hard_filter_analyzer import HardFilterAnalyzer


@dataclass(frozen=True)
class ValidationProfile:
    name: str
    market: str
    terms: tuple[str, ...]
    remote_only: bool = False
    preference: str = "hybrid preferred; onsite considered"


PROFILES = (
    ValidationProfile("IE customer operations/support", "IE", ("customer support", "customer service", "customer operations", "support specialist")),
    ValidationProfile("IE fraud/risk/trust", "IE", ("fraud", "risk", "trust", "financial crime")),
    ValidationProfile("IE fintech/payment operations", "IE", ("payment", "operations", "settlement", "reconciliation")),
    ValidationProfile("IE analyst", "IE", ("analyst",)),
    ValidationProfile("UK operations management", "UK", ("operations manager", "team lead", "complaints manager", "operations lead")),
    ValidationProfile("UK customer success", "UK", ("customer success", "account manager", "customer experience")),
    ValidationProfile("UK compliance/AML", "UK", ("compliance", "aml", "financial crime", "kyc")),
    ValidationProfile("UK remote support", "UK", ("customer support", "customer service", "support specialist"), True, "remote required"),
    ValidationProfile("Europe remote fintech/risk", "EU", ("risk", "fraud", "payment", "operations", "compliance"), True, "remote required"),
    ValidationProfile("Europe customer success/analyst", "EU", ("customer success", "analyst", "account manager")),
)
MARKETS = {
    "IE": r"\b(ireland|dublin|cork|galway|limerick)\b",
    "UK": r"\b(uk|united kingdom|london|manchester|belfast|edinburgh|glasgow|bristol|leeds)\b",
    "EU": r"\b(europe|emea|ireland|dublin|uk|united kingdom|london|manchester|germany|berlin|netherlands|amsterdam|france|paris|spain|madrid|portugal|lisbon|poland|warsaw)\b",
}
BOARDS = (("lever", "zopa", "Zopa"), ("lever", "plaid", "Plaid"),
          ("ashby", "paddle", "Paddle"), ("ashby", "wayflyer", "Wayflyer"))


def assess(jobs, profile):
    candidate = CandidateProfile(current_level="mid", spoken_languages=["english"],
        target_roles=list(profile.terms), hard_constraints=["no night shifts", "no relocation", "no overnight on-call"])
    analyzer = HardFilterAnalyzer(candidate)
    title_matches, plausible, survivors = [], [], []
    reasons = {}
    for job in jobs:
        title = (job.title or "").lower()
        if not any(re.search(r"\b" + re.escape(term) + r"\b", title) for term in profile.terms):
            continue
        title_matches.append(job)
        if not re.search(MARKETS[profile.market], (job.location or "").lower()):
            continue
        if profile.remote_only and job.remote is not True:
            continue
        plausible.append(job)
        seniority = "director" if re.search(r"\b(director|head of|vp|chief)\b", title) else ""
        # Only literal title evidence. No generated job profile or capabilities.
        result = analyzer.analyze(job, JobProfile(job_id=job.id, canonical_role=job.title or "", seniority=seniority))
        if not result["rejected"]:
            survivors.append(job)
        for reason in result["reasons"]:
            reasons[reason] = reasons.get(reason, 0) + 1
    count = len(survivors)
    quality = "strong" if len(plausible) >= 20 and count >= 10 else "acceptable" if count >= 5 else "weak" if count else "insufficient"
    return {"profile": asdict(profile), "pool_size": len(jobs), "title_plausible": len(title_matches),
            "plausible_location_mode": len(plausible), "deterministic_survivors": count,
            "assessment": quality, "rejection_reasons": reasons, "human_attention_verified": None,
            "examples": [{"title": j.title, "company": j.company, "location": j.location, "url": j.url}
                         for j in survivors[:5]]}


class RequestBudget:
    def __init__(self, limit=12):
        self.limit, self.calls = limit, 0

    def session(self):
        budget = self
        class BoundedSession(requests.Session):
            def send(self, request, **kwargs):
                if request.method != "GET" or urlsplit(request.url).hostname not in {"api.lever.co", "api.ashbyhq.com"}:
                    raise RuntimeError("Unapproved validation request.")
                if budget.calls >= budget.limit:
                    from services.job_sources.board_http import BoardError
                    raise BoardError("validation_request_budget")
                budget.calls += 1
                return super().send(request, **kwargs)
        return BoundedSession()


def collect(row, name, budget):
    from services.job_sources.board_http import BoardHTTPClient, BoardError
    from services.job_sources.lever_source import LeverJobSource
    from services.job_sources.ashby_source import AshbyJobSource
    raw_count = 0
    class CountingHTTP:
        def get_json(self, url, *, params):
            nonlocal raw_count
            data = BoardHTTPClient(session_factory=budget.session).get_json(url, params=params)
            records = data if isinstance(data, list) else data.get("jobs", []) if isinstance(data, dict) else []
            raw_count += len(records) if isinstance(records, list) else 0
            return data
    adapter = (LeverJobSource if row.source_type == "lever" else AshbyJobSource)(row, name, CountingHTTP())
    if row.source_type == "lever":
        adapter.MAX_PAGES = 3
    start, calls = time.monotonic(), budget.calls
    error, jobs = None, []
    try:
        jobs = adapter.search(results_per_page=100)
    except Exception as exc:
        error = exc.code if isinstance(exc, BoardError) else "validation_failure"
    return jobs, {"provider": row.source_type, "board": row.source_key,
        "observed_at": datetime.now(timezone.utc).isoformat(), "requests": budget.calls - calls,
        "raw_postings": raw_count, "valid_jobs": len(jobs), "skipped": adapter.skipped_records,
        "duplicate_records": max(0, raw_count - adapter.skipped_records - len(jobs)) if error is None else None,
        "coverage_complete": error is None and adapter.skipped_records == 0,
        "error_code": error, "duration_seconds": round(time.monotonic() - start, 3)}


def validate_live():
    # Override the connection before importing any repository. Never touch the
    # user's persistent pool or use a configured PostgreSQL URL for this slice.
    os.environ["DATABASE_URL"] = ""
    from services import database
    from services.company_repository import CompanyRepository
    from services.company_source_repository import CompanySourceRepository
    from services.source_schedule_service import SourceScheduleService
    from services.source_run_repository import SourceRunRepository
    from services.job_search_repository import JobSearchRepository

    budget = RequestBudget()
    with tempfile.TemporaryDirectory(prefix="workpilot-coverage-") as directory:
        database.DATABASE_FILE = Path(directory) / "validation.db"
        database.initialize_database.cache_clear()
        database.initialize_database()
        rows = []
        for vendor, key, name in BOARDS:
            company = CompanyRepository().get_or_create_company(name)
            rows.append(CompanySourceRepository().upsert_company_source(company.id, vendor, key))
        snapshots, metrics = {}, []
        for row, (_, _, name) in zip(rows, BOARDS):
            snapshots[row.id], metric = collect(row, name, budget)
            metrics.append(metric)

        class Replay:
            def __init__(self, row):
                self.source_type = f"{row.source_type}:{row.id}"
                self.row = row
                self.skipped_records = metrics[rows.index(row)]["skipped"]
            def search(self, **kwargs):
                error = metrics[rows.index(self.row)]["error_code"]
                if error:
                    from services.job_sources.board_http import BoardError
                    raise BoardError(error)
                return snapshots[self.row.id]
        clock = [datetime.now(timezone.utc)]
        service = SourceScheduleService(clock=lambda: clock[0], factories={"lever": Replay, "ashby": Replay})
        first = service.run([], rows)
        skipped = service.run([], rows)
        with database.get_connection() as conn:
            seen_before = [r[0] for r in conn.execute("SELECT last_seen_at FROM job_sources ORDER BY source_id").fetchall()]
        # Second live observations use the same bounded request budget.
        repeat = []
        for row, (_, _, name) in zip(rows, BOARDS):
            jobs, metric = collect(row, name, budget)
            previous = {j.id for j in snapshots[row.id]}
            current = {j.id for j in jobs}
            metric["retained_ids"] = len(previous & current)
            metric["removed_ids"] = len(previous - current) if metric["error_code"] is None else None
            repeat.append(metric)
            snapshots[row.id] = jobs
        metrics_for_report = metrics
        metrics = repeat
        clock[0] += timedelta(hours=8)
        second = service.run([], rows)
        with database.get_connection() as conn:
            records = [dict(r) for r in conn.execute("SELECT * FROM jobs").fetchall()]
            seen_after = [r[0] for r in conn.execute("SELECT last_seen_at FROM job_sources ORDER BY source_id").fetchall()]
        from models.job import Job
        fields = {field for field in Job.__dataclass_fields__}
        pool = [Job(**{**{k: v for k, v in r.items() if k in fields},
                       "remote": bool(r["remote"]) if r["remote"] is not None else None}) for r in records]
        profiles = []
        for i, profile in enumerate(PROFILES):
            result = assess(pool, profile)
            result["discovery_eligible"] = len(JobSearchRepository().list_jobs_to_analyze_for_candidate(
                candidate_id=f"synthetic-validation-{i}", analysis_version="validation-no-ai",
                candidate_signature="synthetic", limit=10000, target_families=list(profile.terms)))
            profiles.append(result)
        return {"validation_time": datetime.now(timezone.utc).isoformat(), "http_requests": budget.calls,
            "providers_first": metrics_for_report, "providers_second": repeat,
            "scheduler_first_replay": first, "scheduler_immediate_replay": skipped,
            "scheduler_second_replay": second, "scheduler_clock": "second replay advances 8 hours; no sleeps",
            "freshness_changed": seen_before != seen_after, "pool_size": len(pool), "profiles": profiles,
            "source_runs": [r for row in rows for r in SourceRunRepository().list_runs(f"{row.source_type}:{row.id}")],
            "ai_calls": 0, "gmail_calls": 0, "postgres_live": "pending"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Permit up to 12 public board HTTP requests.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("Live validation requires explicit --live; unit tests use fixtures instead.")
    result = validate_live()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({"http_requests": result["http_requests"], "pool_size": result["pool_size"],
                      "errors": [m["error_code"] for m in result["providers_first"]]}))


if __name__ == "__main__":
    main()
