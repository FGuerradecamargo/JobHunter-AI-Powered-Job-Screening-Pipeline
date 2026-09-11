from __future__ import annotations

from typing import Any, Callable

from services.candidate_repository import (
    CandidateRepository,
)
from services.career_update_repository import (
    CareerUpdateRepository,
)
from services.career_evidence_builder import (
    build_career_evidence_records,
)
from services.career_evidence_aggregator import (
    aggregate_market_evidence,
)
from services.market_position_service import (
    load_historical_market_signals,
)
from services.database import (
    list_candidate_application_outcomes,
)


class CareerEvidenceService:
    def __init__(
        self,
        *,
        candidate_repository=None,
        career_update_repository=None,
        market_signal_loader: Callable[
            [str],
            list[dict[str, Any]],
        ] = load_historical_market_signals,
        outcome_loader: Callable[
            [str],
            list[dict[str, Any]],
        ] = list_candidate_application_outcomes,
    ) -> None:
        self.candidate_repository = (
            candidate_repository
            or CandidateRepository()
        )

        self.career_update_repository = (
            career_update_repository
            or CareerUpdateRepository()
        )

        self.market_signal_loader = (
            market_signal_loader
        )

        self.outcome_loader = (
            outcome_loader
        )

    def build(
        self,
        candidate_id: str,
    ) -> dict[str, Any]:
        normalized_candidate_id = str(
            candidate_id or ""
        ).strip()

        if not normalized_candidate_id:
            raise ValueError(
                "candidate_id must be non-empty."
            )

        candidate = (
            self.candidate_repository.get(
                normalized_candidate_id
            )
        )

        if candidate is None:
            raise ValueError(
                "Candidate was not found: "
                f"{normalized_candidate_id}"
            )

        career_updates = (
            self.career_update_repository
            .list_for_candidate(
                normalized_candidate_id
            )
        )

        market_signals = (
            self.market_signal_loader(
                normalized_candidate_id
            )
        )

        application_outcomes = (
            self.outcome_loader(
                normalized_candidate_id
            )
        )

        records = (
            build_career_evidence_records(
                candidate=candidate,
                career_updates=(
                    career_updates
                ),
                market_signals=(
                    market_signals
                ),
                application_outcomes=(
                    application_outcomes
                ),
            )
        )

        aggregated_signals = (
            aggregate_market_evidence(
                records
            )
        )

        return {
            "candidate_id": (
                normalized_candidate_id
            ),
            "records": records,
            "market_signals": (
                aggregated_signals
            ),
            "counts": {
                "records": len(
                    records
                ),
                "market_signals": len(
                    aggregated_signals
                ),
                "market_sources": len(
                    {
                        item.source_ref
                        for item in records
                        if (
                            item.evidence_type
                            == "market_signal"
                            and item.source_ref
                        )
                    }
                ),
                "outcomes": len(
                    {
                        item.source_ref
                        for item in records
                        if (
                            item.evidence_type
                            == "application_outcome"
                            and item.source_ref
                        )
                    }
                ),
            },
        }


def build_candidate_career_evidence(
    candidate_id: str,
) -> dict[str, Any]:
    return CareerEvidenceService().build(
        candidate_id
    )
