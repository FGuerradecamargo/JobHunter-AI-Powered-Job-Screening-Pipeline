import json

import pytest

from models.candidate_onboarding import CandidateOnboarding
from services.candidate_profile_generation_service import CandidateProfileGenerationService
from services.candidate_repository import CandidateRepository
from services.career_update_repository import CareerUpdateRepository
from services.profile_snapshot_repository import ProfileSnapshotRepository
from tests.test_v1_onboarding_profile_integration import finalize
from tests.test_workpilot_v1_onboarding_persistence import repo


class Client:
    def __init__(self, preference_as_skill=False):
        self.calls = []
        self.preference_as_skill = preference_as_skill

    def generate(self, prompt):
        self.calls.append(prompt)
        payload = json.loads(prompt.rsplit("\n", 1)[1])
        source_type = "candidate_preference" if self.preference_as_skill else "professional_experience"
        ref = next(item["ref"] for item in payload["sources"] if item["source_type"] == source_type)
        return json.dumps({"capabilities": [{"capability_id": "cap", "label": "Supported capability",
            "evidence_refs": [ref]}], "checkpoint": {"current_position": "Grounded profile"}})


def service(repo, client):
    finalize(repo)
    repo.save_onboarding(CandidateOnboarding("a", desired_next_work="Develop software"))
    return CandidateProfileGenerationService(client, repo, CandidateRepository(), CareerUpdateRepository())


def test_profile_page_generation_persists_official_snapshot_and_reuses_signature(repo):
    client = Client()
    generator = service(repo, client)
    view = generator.generate("a", "Fixture")
    snapshot = ProfileSnapshotRepository().current_candidate("a")
    assert snapshot.capabilities[0].label in view.proven_capabilities
    assert snapshot.capabilities[0].evidence_refs[0].startswith("professional_experience:")
    assert any(ref.startswith("candidate_preference:") for ref in snapshot.source_refs)
    assert generator.generate("a", "Fixture") == view
    assert len(client.calls) == 1
    assert ProfileSnapshotRepository().current_candidate("b") is None


def test_preferences_cannot_be_promoted_to_professional_evidence(repo):
    generator = service(repo, Client(True))
    with pytest.raises(ValueError, match="Invalid structured"):
        generator.generate("a", "Fixture")
    assert ProfileSnapshotRepository().current_candidate("a") is None
