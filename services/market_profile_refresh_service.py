from __future__ import annotations

import json

from models.market_profile import MarketSegment
from models.profile_interpretation import (
    AI_JOB_PROFILE_SCHEMA_VERSION,
    JobRequirementStatus,
)
from services.database import utc_now
from services.job_source_repository import JobSourceRepository
from services.market_job_observation import (
    PUBLIC_PROVIDERS,
    public_market_observation,
)
from services.market_profile_builder import build_market_profile
from services.market_profile_repository import MarketProfileRepository
from services.profile_snapshot_repository import ProfileSnapshotRepository
from services.role_family_normalizer import normalize_role_family


_ELIGIBLE_NEED_STATES = {
    JobRequirementStatus.REQUIRED,
    JobRequirementStatus.PREFERRED,
    JobRequirementStatus.USEFUL,
}


class MarketProfileRefreshService:
    """Build global Market snapshots from independently public job evidence.

    CandidateProfile, HiringCase, candidate analyses and private observations
    never enter this service.
    """

    def __init__(
        self,
        *,
        source_repository=None,
        profile_repository=None,
        market_repository=None,
        clock=utc_now,
    ):
        self.sources = (
            source_repository
            or JobSourceRepository()
        )
        self.profiles = (
            profile_repository
            or ProfileSnapshotRepository()
        )
        self.markets = (
            market_repository
            or MarketProfileRepository()
        )
        self.clock = clock

    def _job_profile_signals(
        self,
        job_id: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        try:
            hard_facts = self.sources.load_job_hard_facts(
                job_id
            )
        except ValueError:
            return (), ()

        profile = self.profiles.job_for_signature(
            job_id,
            hard_facts.job_signature,
            AI_JOB_PROFILE_SCHEMA_VERSION,
        )

        if profile is None:
            return (), ()

        capabilities = tuple(
            need.label
            for need in profile.needs
            if (
                need.requirement_status
                in _ELIGIBLE_NEED_STATES
                and str(need.label or "").strip()
            )
        )

        return (
            capabilities,
            tuple(profile.tools_as_means),
        )

    def _project_row(self, row):
        provider = str(
            row.get("source_type") or ""
        ).strip().casefold()

        source_id = str(
            row.get("external_id") or ""
        ).strip()

        role_family = normalize_role_family(
            row.get("sub_category")
        )

        if (
            provider not in PUBLIC_PROVIDERS
            or not source_id
            or not role_family
        ):
            return None

        try:
            payload = json.loads(
                row.get("payload_json") or "{}"
            )
        except (TypeError, ValueError):
            return None

        if not isinstance(payload, dict):
            return None

        capabilities, tools = (
            self._job_profile_signals(
                str(row.get("job_id") or "")
            )
        )

        facts = {
            "role_family": role_family,
            "location": str(
                payload.get("location") or ""
            ).strip(),
            "capabilities": capabilities,
            "tools": tools,
        }

        if payload.get("remote") is True:
            facts["work_mode"] = "Remote"

        salary = str(
            payload.get("salary") or ""
        ).strip()

        if salary:
            facts["compensation"] = salary

        observed_at = str(
            row.get("last_seen_at")
            or row.get("updated_at")
            or row.get("created_at")
            or ""
        ).strip()

        if not observed_at:
            return None

        url = str(
            payload.get("url") or ""
        ).strip()

        identity = {}

        if url.startswith(
            ("https://", "http://")
        ):
            identity["public_url"] = url

        try:
            return public_market_observation(
                provider=provider,
                source_id=source_id,
                user_id=None,
                observed_at=observed_at,
                identity=identity,
                facts=facts,
            )
        except ValueError:
            # An invalid public URL must not make the evidence public by
            # assertion. Fall back only to the provider's explicit source ID.
            return public_market_observation(
                provider=provider,
                source_id=source_id,
                user_id=None,
                observed_at=observed_at,
                identity={},
                facts=facts,
            )

    def observations(self):
        projected = []

        for row in self.sources.list_public_market_rows():
            item = self._project_row(row)

            if item is not None:
                projected.append(item)

        return tuple(projected)

    def refresh(self):
        observations = self.observations()

        role_families = sorted(
            {
                normalize_role_family(
                    item.role_family
                )
                for item in observations
                if normalize_role_family(
                    item.role_family
                )
            },
            key=str.casefold,
        )

        if not role_families:
            return ()

        now = self.clock()
        refreshed = []

        for role_family in role_families:
            segment = MarketSegment(
                role_family=role_family
            )

            previous = self.markets.current(
                segment
            )

            profile = build_market_profile(
                observations=list(observations),
                segment=segment,
                created_at=now,
                previous=previous,
            )

            if (
                previous is None
                or profile.source_signature
                != previous.source_signature
            ):
                self.markets.save(profile)

            refreshed.append(profile)

        return tuple(refreshed)
