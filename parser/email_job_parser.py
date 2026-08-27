from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlparse,
    urlunparse,
)

from bs4 import BeautifulSoup

from models.job import Job
from parser.job_parser import extract_jobs_from_html


@dataclass(frozen=True)
class ParsedEmailJobs:
    source: str
    jobs: dict[str, Job]


SOURCE_DOMAINS = {
    "linkedin": (
        "linkedin.com",
    ),
    "indeed": (
        "indeed.com",
        "indeed.ie",
        "indeed.co.uk",
    ),
    "irishjobs": (
        "irishjobs.ie",
    ),
    "jobs_ie": (
        "jobs.ie",
    ),
    "totaljobs": (
        "totaljobs.com",
    ),
    "reed": (
        "reed.co.uk",
    ),
}


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "trk",
    "tracking",
    "ref",
    "source",
}


def detect_email_source(
    sender: str,
    html: str,
) -> str:
    haystack = (
        f"{sender or ''} {html or ''}"
    ).lower()

    for source, domains in SOURCE_DOMAINS.items():
        if any(
            domain in haystack
            for domain in domains
        ):
            return source

    return "unknown"


def normalize_job_url(
    url: str,
) -> str:
    url = (url or "").strip()

    if not url:
        return ""

    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return ""

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if key.lower()
        not in TRACKING_PARAMS
    ]

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            urlencode(filtered_query),
            "",
        )
    )


def build_external_job_id(
    source: str,
    url: str,
) -> str:
    digest = hashlib.sha256(
        f"{source}:{url}".encode(
            "utf-8"
        )
    ).hexdigest()[:24]

    return f"{source}_{digest}"


def looks_like_job_url(
    source: str,
    url: str,
) -> bool:
    lowered = url.lower()

    patterns = {
        "indeed": (
            "/viewjob",
            "/rc/clk",
            "jk=",
        ),
        "irishjobs": (
            "/job/",
            "/jobs/",
        ),
        "jobs_ie": (
            "/job/",
            "/jobs/",
        ),
        "totaljobs": (
            "/job/",
            "/jobs/",
        ),
        "reed": (
            "/jobs/",
            "/job/",
        ),
    }

    return any(
        pattern in lowered
        for pattern in patterns.get(
            source,
            (),
        )
    )


def extract_generic_jobs(
    html: str,
    source: str,
) -> dict[str, Job]:
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    jobs: dict[str, Job] = {}

    for link in soup.find_all("a"):
        href = link.get("href")

        if not href:
            continue

        clean_url = normalize_job_url(
            href
        )

        if not clean_url:
            continue

        parsed = urlparse(
            clean_url
        )

        domains = SOURCE_DOMAINS.get(
            source,
            (),
        )

        if not any(
            domain in parsed.netloc
            for domain in domains
        ):
            continue

        if not looks_like_job_url(
            source,
            clean_url,
        ):
            continue

        text = link.get_text(
            " ",
            strip=True,
        )

        if not text:
            continue

        title = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        if len(title) < 3:
            continue

        if len(title) > 180:
            title = title[:180].strip()

        job_id = build_external_job_id(
            source,
            clean_url,
        )

        remote = (
            "remote"
            in title.lower()
        )

        existing = jobs.get(
            job_id
        )

        if (
            existing is None
            or len(title)
            > len(existing.raw_text)
        ):
            jobs[job_id] = Job(
                id=job_id,
                raw_text=title,
                url=clean_url,
                title=title,
                remote=remote,
            )

    return jobs




INDEED_NON_JOB_LABELS = {
    "view all jobs",
    "since yesterday",
    "for last 7 days",
    "edit this job alert",
    "indeed terms of service",
    "privacy policy",
    "help centre",
    "help center",
    "manage job alerts",
    "unsubscribe from this job alert",
}


def extract_indeed_jobs(
    html: str,
) -> dict[str, Job]:
    """
    Extract jobs from Indeed alert emails.

    Indeed job-alert links use engage.indeed.com redirect URLs,
    so URL-pattern matching alone is not sufficient.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    jobs: dict[str, Job] = {}
    seen_hrefs: set[str] = set()

    for link in soup.find_all("a"):
        href = (
            link.get("href")
            or ""
        ).strip()

        if not href:
            continue

        if href in seen_hrefs:
            continue

        seen_hrefs.add(href)

        parsed_url = urlparse(
            href
        )

        if (
            "engage.indeed.com"
            not in parsed_url.netloc.lower()
        ):
            continue

        text_parts = [
            re.sub(
                r"\s+",
                " ",
                str(part),
            ).strip()
            for part in link.stripped_strings
            if str(part).strip()
        ]

        if not text_parts:
            continue

        label = " ".join(
            text_parts
        ).strip()

        lowered = label.lower()

        if lowered in INDEED_NON_JOB_LABELS:
            continue

        if any(
            lowered.startswith(
                excluded
            )
            for excluded in (
                "view all jobs",
                "edit this job alert",
                "manage job alerts",
                "unsubscribe",
                "indeed terms",
                "privacy policy",
                "help centre",
                "help center",
            )
        ):
            continue

        # Real job cards contain considerably more content
        # than navigation/tracking links.
        if len(label) < 30:
            continue

        # The first visible text node in an Indeed card
        # is normally the job title.
        title = text_parts[0]

        if (
            len(title) < 3
            or len(title) > 180
        ):
            continue

        clean_url = href

        # Build a stable identity from the visible job-card
        # evidence rather than Indeed's per-email tracking URL.
        identity_text = "|".join(
            part.lower()
            for part in text_parts[:4]
        )

        digest = hashlib.sha256(
            (
                "indeed:"
                + identity_text
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:24]

        job_id = (
            "indeed_"
            + digest
        )

        remote = (
            "remote"
            in label.lower()
        )

        jobs[job_id] = Job(
            id=job_id,
            raw_text=label,
            url=clean_url,
            title=title,
            remote=remote,
        )

    return jobs


def extract_jobs_from_email(
    html: str,
    sender: str = "",
) -> ParsedEmailJobs:
    source = detect_email_source(
        sender=sender,
        html=html,
    )

    if source == "linkedin":
        return ParsedEmailJobs(
            source="linkedin",
            jobs=extract_jobs_from_html(
                html
            ),
        )

    if source == "indeed":
        return ParsedEmailJobs(
            source="indeed",
            jobs=extract_indeed_jobs(
                html
            ),
        )

    if source in SOURCE_DOMAINS:
        return ParsedEmailJobs(
            source=source,
            jobs=extract_generic_jobs(
                html=html,
                source=source,
            ),
        )

    return ParsedEmailJobs(
        source="unknown",
        jobs={},
    )
