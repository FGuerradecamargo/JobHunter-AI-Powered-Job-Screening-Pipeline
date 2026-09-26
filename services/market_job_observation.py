"""Public-source projection only; never project candidate analyses or private imports."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from models.market_profile import MarketJobObservation


PUBLIC_PROVIDERS = frozenset({"adzuna", "jooble", "lever", "ashby", "company"})


def global_market_job_identity(*, company_id="", requisition_id="", public_url="",
                               provider="", source_id="", company="", title="",
                               location="", context="") -> str:
    """Exact identity only. Context must distinguish otherwise ambiguous vacancies."""
    if company_id and requisition_id:
        identity = ["requisition", company_id, requisition_id]
    elif public_url:
        parsed = urlsplit(public_url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Public job URL is invalid.")
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if not k.casefold().startswith("utm_") and k.casefold() not in {"gclid", "fbclid"}]
        identity = ["url", urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path,
                                      urlencode(sorted(query)), ""))]
    elif provider and source_id:
        identity = ["provider", provider.casefold(), source_id]
    elif all((company, title, location, context)):
        identity = ["context", *[" ".join(v.split()).casefold()
                                 for v in (company, title, location, context)]]
    else:
        raise ValueError("Insufficient evidence for global job identity.")
    return "market-job:" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def public_market_observation(*, provider: str, source_id: str, user_id,
                              observed_at: str, identity: dict, facts: dict) -> MarketJobObservation:
    """Caller supplies an independently public source's facts, not shared jobs text.

    A matching public source does not declassify a private observation's payload.
    Unknown fields are omitted, never inferred from candidate data.
    """
    provider = provider.strip().casefold()
    if user_id is not None or provider not in PUBLIC_PROVIDERS or not source_id.strip():
        raise ValueError("Only independently public source evidence is eligible.")
    allowed = {"role_family", "location", "seniority", "domain", "work_mode",
               "employment_type", "capabilities", "tools", "compensation"}
    if set(facts) - allowed:
        raise ValueError("Unsupported market observation fields.")
    return MarketJobObservation(
        job_id=global_market_job_identity(provider=provider, source_id=source_id, **identity),
        observed_at=observed_at, source_refs=(f"public:{provider}:{source_id}",), **facts,
    )
