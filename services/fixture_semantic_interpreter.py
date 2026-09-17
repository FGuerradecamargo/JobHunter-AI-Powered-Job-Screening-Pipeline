"""Exact, immutable offline fixtures. Missing interpretations abstain, never guess."""
from copy import deepcopy

from models.semantic_evidence import SemanticSupportResult
from models.structured_interpretation import ValidationStatus
from services.semantic_evidence_boundary import signature, validate_semantic_support


class FixtureSemanticInterpreter:
    def __init__(self, fixtures):
        self._fixtures = deepcopy(fixtures)

    def evaluate_semantic_support(self, request):
        return deepcopy(self._fixtures.get(signature(request)))

    def evaluate(self, request):
        snapshot = deepcopy(request)
        raw = self.evaluate_semantic_support(snapshot)
        if raw is None:
            return SemanticSupportResult(signature(snapshot), ValidationStatus.UNAVAILABLE,
                                         issue_codes=("fixture_unavailable",))
        return validate_semantic_support(snapshot, raw)
