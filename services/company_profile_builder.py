from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from models.company_profile import (
    CompanyProfileDraft,
    CompanyProfileSnapshot,
    CompanyPublicSource,
    validate_grounding,
)


def _signature(sources: tuple[CompanyPublicSource, ...], draft) -> str:
    payload = [
        {
            "ref": item.ref,
            "source_type": item.source_type,
            "title": item.title,
            "published_at": item.published_at,
            "summary": item.summary,
        }
        for item in sorted(
            sources,
            key=lambda item: item.ref,
        )
    ]
    return hashlib.sha256(
        json.dumps(
            {"sources": payload, "draft": asdict(draft)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def build_company_profile(
    *,
    company_id: str,
    sources: tuple[CompanyPublicSource, ...],
    draft: CompanyProfileDraft,
    created_at: str,
    previous: CompanyProfileSnapshot | None = None,
) -> CompanyProfileSnapshot:
    if not sources:
        raise ValueError(
            "Company profile requires at least one public source."
        )
    company_id = company_id.strip()
    validate_grounding(company_id, sources, draft)
    if previous is not None and previous.company_id != company_id:
        raise ValueError("Company history scope mismatch.")
    sources = tuple(sorted({item.ref: item for item in sources}.values(), key=lambda item: item.ref))
    signature = _signature(sources, draft)
    if (
        previous is not None
        and previous.company_id == company_id
        and previous.source_signature == signature
    ):
        return previous

    return CompanyProfileSnapshot(
        company_id=company_id,
        profile_version=(
            previous.profile_version + 1
            if previous
            else 1
        ),
        supersedes_version=(
            previous.profile_version
            if previous
            else None
        ),
        source_signature=signature,
        created_at=created_at,
        source_refs=tuple(
            item.ref
            for item in sources
        ),
        what_they_do=draft.what_they_do,
        products_services=draft.products_services,
        market_context=draft.market_context,
        size_context=draft.size_context,
        public_culture_signals=draft.public_culture_signals,
        public_strategy_priorities=draft.public_strategy_priorities,
        recent_developments=draft.recent_developments,
        role_context=draft.role_context,
        uncertainties=draft.uncertainties,
        claims=draft.claims,
        sources=sources,
    )
