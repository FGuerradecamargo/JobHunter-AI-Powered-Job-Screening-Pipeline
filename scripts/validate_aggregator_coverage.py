"""Opt-in, bounded validation; never imports AI or touches the persistent DB."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit, quote, quote_plus

import requests
from dotenv import load_dotenv

from scripts.validate_launch_coverage import PROFILES, assess
from services.job_sources.board_http import BoardError


PLAN = [("ie", "customer support"), ("ie", "fraud risk"),
        ("ie", "payments operations"), ("ie", "analyst compliance"),
        ("gb", "operations"), ("gb", "customer success"),
        ("gb", "compliance AML"), ("gb", "remote support")]


def safe_output(value, secrets):
    if isinstance(value, dict):
        return {k: safe_output(v, secrets) for k, v in value.items() if k != "url"}
    if isinstance(value, list):
        return [safe_output(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                for form in {secret, quote(secret, safe=""), quote_plus(secret)}:
                    value = value.replace(form, "[REDACTED]")
    return value


class SafeHTTP:
    """No redirects/retries, bounded bytes, no exception text or attached request."""
    def __init__(self, vendor, session_factory=requests.Session):
        self.vendor, self.session_factory = vendor, session_factory
        self.attempts = self.successes = 0
        self.raw_count = 0

    def request(self, url, **kwargs):
        parsed = urlsplit(url)
        host = "api.adzuna.com" if self.vendor == "adzuna" else "jooble.org"
        if parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.password:
            raise BoardError("unapproved_destination")
        if self.attempts >= 12:
            raise BoardError("validation_budget")
        self.attempts += 1
        self.raw_count = 0
        try:
            with self.session_factory() as session:
                session.trust_env = False
                with session.request("GET" if self.vendor == "adzuna" else "POST", url,
                        **{k: v for k, v in kwargs.items() if k != "timeout"},
                        timeout=(5, 25), allow_redirects=False, stream=True) as response:
                    if not 200 <= response.status_code < 300:
                        raise BoardError("http_" + str(response.status_code))
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 4 * 1024 * 1024:
                            raise BoardError("response_too_large")
                        chunks.append(chunk)
                    data = json.loads(b"".join(chunks))
                    key = "results" if self.vendor == "adzuna" else "jobs"
                    if not isinstance(data, dict) or not isinstance(data.get(key), list):
                        raise BoardError("response_shape")
                    self.raw_count = len(data[key])
                    self.successes += 1
                    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: data)
        except BoardError:
            raise
        except Exception:
            raise BoardError("transport_or_decode_failure") from None


def collect(vendor, market, query, http):
    from services.job_sources import adzuna_source, jooble_source
    from services.job_observation import normalize_observation
    module = adzuna_source if vendor == "adzuna" else jooble_source
    started = time.monotonic()
    before = http.attempts
    jobs, error, skipped = [], None, 0
    http.raw_count = 0
    try:
        adapter = module.AdzunaJobSource(market) if vendor == "adzuna" else module.JoobleJobSource()
        with patch.object(module, "requests", SimpleNamespace(get=http.request, post=http.request)):
            values = adapter.search(query, "Ireland" if market == "ie" else "United Kingdom", results_per_page=20)
        for value in values:
            try:
                normalized = normalize_observation(value, vendor).job
                if not normalized.title or not normalized.url:
                    raise ValueError()
                jobs.append(normalized)
            except Exception:
                skipped += 1
        skipped += max(0, http.raw_count - len(values))
    except Exception as exc:
        error = exc.code if isinstance(exc, BoardError) else "adapter_failure"
    return jobs, dict(provider=vendor, market=market, query=query, requests=http.attempts-before,
        raw_records=http.raw_count, valid_jobs=len(jobs), skipped=skipped if error is None else None,
        unique_provider_ids=len({j.id for j in jobs}), duplicate_records=len(jobs)-len({j.id for j in jobs}),
        error_code=error, duration_seconds=round(time.monotonic()-started, 3),
        observed_at=datetime.now(timezone.utc).isoformat(), coverage_complete=False)


def run(jooble_region=None):
    load_dotenv()
    keys = ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "JOOBLE_API_KEY")
    secrets = [os.getenv(k) or "" for k in keys]
    presence = {k: bool(v.strip()) for k, v in zip(keys, secrets)}
    if not all(presence.values()):
        return {"credentials_present": presence, "status": "preflight_blocked"}
    os.environ["DATABASE_URL"] = ""
    from services import database
    from services.source_schedule_service import SourceScheduleService
    from services.job_sources.provider import ProviderConfig
    from models.job import Job

    transports = {v: SafeHTTP(v) for v in ("adzuna", "jooble")}
    plans = {"adzuna": PLAN}
    if jooble_region:
        plans["jooble"] = [p for p in PLAN if p[0] == jooble_region]
    batches, first, repeat = {}, [], []
    for vendor, plan in plans.items():
        for market, query in plan:
            jobs, metric = collect(vendor, market, query, transports[vendor])
            batches[(vendor, market, query)] = jobs
            first.append(metric)
    with tempfile.TemporaryDirectory(prefix="workpilot-aggregator-") as directory:
        database.DATABASE_FILE = Path(directory) / "validation.db"
        database.initialize_database.cache_clear()
        database.initialize_database()
        clock = [datetime.now(timezone.utc)]
        metrics = first

        class Replay:
            def __init__(self, vendor):
                self.source_type = vendor
            def search(self, keywords, **kwargs):
                market, query = keywords.split("|", 1)
                metric = next(m for m in metrics if (m["provider"], m["market"], m["query"]) == (self.source_type, market, query))
                self.skipped_records = metric["skipped"] or 0
                if metric["error_code"]:
                    raise BoardError(metric["error_code"])
                return batches[(self.source_type, market, query)]

        def configs(selected):
            return [ProviderConfig(v, lambda v=v: Replay(v), query_plan=lambda selected=plan, **kw:
                    [{"query": m+"|"+q} for m, q in selected]) for v, plan in selected.items()]

        scheduler = SourceScheduleService(clock=lambda: clock[0])
        initial = scheduler.run(configs(plans), [])
        immediate = scheduler.run(configs(plans), [])
        with database.get_connection() as conn:
            initial_ids = {r["id"] for r in conn.execute("SELECT id FROM jobs")}
            before_seen = {r["job_id"]: r["last_seen_at"] for r in conn.execute("SELECT * FROM job_sources")}
        subset = {v: [plan[0], plan[-1]] for v, plan in plans.items()}
        for vendor, plan in subset.items():
            for market, query in plan:
                key = (vendor, market, query)
                previous = {j.id for j in batches[key]}
                jobs, metric = collect(vendor, market, query, transports[vendor])
                metric["retained_ids"] = len(previous & {j.id for j in jobs})
                metric["previous_ids"] = len(previous)
                batches[key] = jobs
                repeat.append(metric)
        metrics = repeat
        clock[0] += timedelta(hours=25)
        second = scheduler.run(configs(subset), [])
        with database.get_connection() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM jobs")]
            sources = [dict(r) for r in conn.execute("SELECT * FROM job_sources")]
        pool = [Job(**{**{k:v for k,v in r.items() if k in Job.__dataclass_fields__},
                       "remote": bool(r["remote"]) if r["remote"] is not None else None}) for r in rows]
        by_source = {v: {s["job_id"] for s in sources if s["source_type"] == v} for v in plans}
        profiles = []
        for profile in PROFILES:
            result = assess(pool, profile)
            result["by_provider"] = {v: assess([j for j in pool if j.id in ids], profile) for v, ids in by_source.items()}
            result["rejected_examples"] = []
            for job in pool:
                single = assess([job], profile)
                if single["plausible_location_mode"] and not single["deterministic_survivors"]:
                    result["rejected_examples"].append({"title":job.title,"location":job.location,"reasons":single["rejection_reasons"]})
            result["rejected_examples"] = result["rejected_examples"][:5]
            profiles.append(result)
        signatures = Counter(((j.title or "").casefold().strip(), (j.company or "").casefold().strip(),
                              (j.location or "").casefold().strip()) for j in pool)
        result = dict(credentials_present=presence, providers_first=first, providers_repeat=repeat,
            requests={v:dict(attempted=h.attempts, successful=h.successes) for v,h in transports.items()},
            jooble_region=jooble_region or "unverified; no requests authorized without scope",
            scheduler_initial_replay=initial, scheduler_immediate_replay=immediate, scheduler_repeat_replay=second,
            scheduler_clock="repeat replay advances 25 hours; collection timestamps are actual UTC",
            pool_size=len(pool), initial_pool_size=len(initial_ids),
            canonical_ids_preserved=initial_ids.issubset({j.id for j in pool}),
            provenance_count=len(sources), provider_pool_counts={v:len(ids) for v,ids in by_source.items()},
            cross_provider_shared_jobs=len(set.intersection(*by_source.values())) if len(by_source)>1 else None,
            likely_duplicate_extra_rows=sum(n-1 for n in signatures.values() if n>1),
            freshness_rows_advanced=sum(s["last_seen_at"]>before_seen.get(s["job_id"],s["last_seen_at"]) for s in sources),
            profiles=profiles, employer_baseline="Historical metrics only; no full replay retained, no combined-pool claim",
            ai_calls=0, gmail_calls=0)
    return safe_output(result, secrets)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--jooble-region", choices=["ie", "gb"], help="Only set after key scope is confirmed.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("Explicit --live authorization required.")
    logging.disable(logging.CRITICAL)
    try:
        result = run(args.jooble_region)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"status":"finished", "requests":result.get("requests"), "pool_size":result.get("pool_size")}))
    except Exception:
        print('{"status":"validation_failed"}')
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
