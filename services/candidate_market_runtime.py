from __future__ import annotations

from services.candidate_market_service import CandidateMarketService
from services.market_profile_repository import MarketProfileRepository
from services.profile_snapshot_repository import ProfileSnapshotRepository
from services.role_family_normalizer import role_family_key


def load_candidate_market_runtime(
    candidate_id: str,
    *,
    candidate_repository=None,
    market_repository=None,
):
    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        raise ValueError("candidate_id is required.")

    candidates = candidate_repository or ProfileSnapshotRepository()
    markets = market_repository or MarketProfileRepository()

    candidate = candidates.current_candidate(candidate_id)
    if candidate is None:
        return {
            "status": "candidate_unavailable",
            "candidate_profile": None,
            "objectives": (),
            "segments": (),
        }

    if candidate.candidate_id != candidate_id:
        raise PermissionError("Candidate profile scope mismatch.")

    objectives = tuple(
        dict.fromkeys(
            value.strip()
            for value in candidate.objectives
            if str(value or "").strip()
        )
    )

    if not objectives:
        return {
            "status": "direction_unavailable",
            "candidate_profile": candidate,
            "objectives": (),
            "segments": (),
        }

    objective_keys = {
        role_family_key(value)
        for value in objectives
        if role_family_key(value)
    }

    service = CandidateMarketService(
        candidate_repository=candidates,
        market_repository=markets,
    )

    segments = []

    for market in markets.list_current():
        role_key = role_family_key(market.segment.role_family)

        if not role_key or role_key not in objective_keys:
            continue

        assessment, plan = service.build(
            candidate_id,
            market.segment,
        )

        segments.append(
            {
                "market_profile": market,
                "assessment": assessment,
                "plan": plan,
            }
        )

    return {
        "status": "ok" if segments else "market_unavailable",
        "candidate_profile": candidate,
        "objectives": objectives,
        "segments": tuple(segments),
    }
