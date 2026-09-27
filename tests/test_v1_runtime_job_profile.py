import json
from dataclasses import replace

import pytest

from services.ai.job_profile_service import JobProfileService
from services.job_profile_manager import JobProfileManager
from services.profile_snapshot_repository import ProfileSnapshotRepository
from services.job_source_repository import JobSourceRepository
from tests.test_v1_job_observation_authority import ingest
from tests.test_source_v2_foundation import job


class FakeClient:
    def __init__(self, bad_ref=False):
        self.calls = []
        self.bad_ref = bad_ref

    def generate(self, prompt):
        self.calls.append(prompt)
        facts = json.loads(prompt.rsplit("\n", 1)[1])
        ref = "invented" if self.bad_ref else facts["facts"][0]["fact_id"]
        return json.dumps({"needs": [{"need_id": "n", "label": "Build tools",
            "importance": "core", "authority": "explicit", "hard_fact_refs": [ref],
            "requirement_status": "unknown", "substitutability": "unknown"}],
            "problem_to_solve": "Build tools"})


def test_search_job_profile_facade_uses_official_snapshots_not_legacy_cache():
    ingest(job())
    client = FakeClient()
    manager = JobProfileManager(JobProfileService(client))
    first = manager.get_or_create(job(), candidate_id="fixture")
    assert first.must_have_capabilities == []  # Unknown requirement is not mandatory.
    official = ProfileSnapshotRepository().current_job(job().id)
    assert official is not None and official.needs[0].need_id == "n"
    assert manager.get_or_create(job()) == first
    assert len(client.calls) == 1
    ingest(replace(job(), description="Updated source"))
    manager.get_or_create(job())
    assert len(client.calls) == 2
    assert ProfileSnapshotRepository().current_job(job().id).profile_version == 2


def test_unproven_legacy_job_never_triggers_profile_ai():
    from services import database
    database.upsert_raw_job(job())
    client = FakeClient()
    with pytest.raises(ValueError, match="unavailable"):
        JobProfileManager(JobProfileService(client)).get_or_create(job())
    assert client.calls == []


def test_unknown_job_ref_is_rejected_before_snapshot_persistence():
    ingest(job())
    with pytest.raises(ValueError, match="unknown hard-fact"):
        JobProfileManager(JobProfileService(FakeClient(True))).get_or_create(job())
    assert ProfileSnapshotRepository().current_job(job().id) is None


def test_private_job_profile_requires_candidate_ownership():
    from models.candidate import Candidate
    from services.candidate_repository import CandidateRepository
    from services.user_repository import UserRepository
    CandidateRepository().save(Candidate(id="a", name="Fixture", current_role="", current_level="", professional_summary=""))
    owner = UserRepository().create("owner@example.test", "Fixture", candidate_id="a")
    ingest(job(), "manual", owner.id)
    private_id = JobSourceRepository().list_by_user(owner.id)[0]
    manager = JobProfileManager(JobProfileService(FakeClient()))
    for candidate_id in (None, "other"):
        with pytest.raises(ValueError, match="unavailable"):
            manager.get_official(private_id, candidate_id=candidate_id)
    assert manager.get_official(private_id, candidate_id="a").job_id == private_id


@pytest.mark.parametrize("mutation", ["duplicate", "empty", "hard_blocker"])
def test_invalid_needs_never_enter_official_cache(mutation):
    ingest(job())
    class Invalid(FakeClient):
        def generate(self, prompt):
            payload = json.loads(super().generate(prompt))
            if mutation == "duplicate":
                payload["needs"] *= 2
            elif mutation == "empty":
                payload["needs"][0]["label"] = ""
            else:
                payload["needs"][0]["hard_blocker"] = True
            return json.dumps(payload)
    with pytest.raises(ValueError):
        JobProfileManager(JobProfileService(Invalid())).get_or_create(job())
    assert ProfileSnapshotRepository().current_job(job().id) is None
