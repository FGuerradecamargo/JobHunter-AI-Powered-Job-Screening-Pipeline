from __future__ import annotations

from dataclasses import dataclass, replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from models.job import Job


def is_personal_source(source_type: str) -> bool:
    return source_type in {"gmail", "manual", "import", "manual_import", "private", "user"} or source_type.startswith(("gmail_", "gmail:", "manual:", "private:", "user:"))


def canonical_observation_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Job observation URL is invalid.")
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.casefold().startswith("utm_") and k.casefold() not in {"gclid", "fbclid"}]
    # Fragments can identify distinct vacancies in client-routed ATS pages.
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path,
                       urlencode(sorted(query)), parsed.fragment))


@dataclass(frozen=True)
class JobObservation:
    source_type: str
    external_id: str
    job: Job


def normalize_observation(job: Job, source_type: str) -> JobObservation:
    source_type = str(source_type or "").strip().lower()
    external_id = str(job.id or "").strip()
    title = str(job.title or "").strip()
    if not source_type or not external_id or not title:
        raise ValueError("Job observation requires source, identifier and title.")
    url = str(job.url or "").strip()
    url = canonical_observation_url(url)
    job_id = external_id if external_id.startswith(source_type + ":") else source_type + ":" + external_id
    normalized = replace(
        job, id=job_id, title=title, url=url,
        company=str(job.company or "").strip() or None,
        location=str(job.location or "").strip() or None,
        description=str(job.description or "").strip() or None,
        raw_text=str(job.raw_text or "").strip(),
        salary=str(job.salary).strip() if job.salary is not None else None,
    )
    return JobObservation(source_type, external_id, normalized)
