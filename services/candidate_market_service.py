"""Official V1 relationship projection; legacy candidate history is not Market."""
from services.candidate_market_builder import build_candidate_market, build_improvement_plan


class CandidateMarketService:
    def __init__(self, *, candidate_repository, market_repository):
        self.candidates = candidate_repository
        self.markets = market_repository

    def build(self, candidate_id, segment):
        """Caller supplies the authorized active candidate, as in other profile services.

        Missing snapshots remain unavailable; never fall back to candidate-derived
        global market evidence or generate profiles implicitly.
        """
        candidate_id = str(candidate_id or "").strip()
        if not candidate_id:
            raise ValueError("candidate_id is required.")
        candidate = self.candidates.current_candidate(candidate_id)
        if candidate is None:
            raise ValueError("Candidate profile is not available.")
        if candidate.candidate_id != candidate_id:
            raise PermissionError("Candidate profile scope mismatch.")
        market = self.markets.current(segment)
        if market is None:
            raise ValueError("Global market profile is not available.")
        if market.segment != segment:
            raise ValueError("Market profile segment mismatch.")
        assessment = build_candidate_market(candidate_profile=candidate, market_profile=market)
        return assessment, build_improvement_plan(assessment)
