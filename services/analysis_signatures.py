import hashlib
import json
from typing import Any


def build_signature(
    data: dict[str, Any],
) -> str:
    serialized = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def build_job_signature_from_values(
    *,
    job_id,
    title,
    company,
    location,
    remote,
    salary,
    description,
    url,
) -> str:
    return build_signature(
        {
            "id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "remote": remote,
            "salary": salary,
            "description": description,
            "url": url,
        }
    )


def build_job_signature(job) -> str:
    return build_job_signature_from_values(
        job_id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        remote=job.remote,
        salary=job.salary,
        description=job.description,
        url=job.url,
    )
