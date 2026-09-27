import pytest

from services.application_contract_service import ApplicationContractService
from services.application_context_service import ApplicationContextService
from services.candidate_profile_source import load_confirmed_candidate_profile_input
from services.career_update_repository import CareerUpdateRepository
from tests.test_v1_search_hiring_case_integration import search_service, RelationshipClient, offline
from tests.test_workpilot_v1_onboarding_persistence import repo
from tests.test_source_v2_foundation import job


def test_cv_context_uses_confirmed_answers_and_same_hiring_case_refs(repo):
    service = search_service(repo, RelationshipClient())
    assert service.analyze_pending("a", limit=1)["failed"] == 0
    contract = ApplicationContractService().build("a", job().id)
    context = ApplicationContextService().build("a", job().id)
    _, sources = load_confirmed_candidate_profile_input("a", repo, CareerUpdateRepository())
    source_text = {source.ref: source.summary for source in sources}
    assert contract.eligible and context.eligible
    assert contract.evidence_refs and context.direct_evidence
    assert all(item.statement == source_text[item.evidence_ref] for item in contract.evidence_refs)
    assert all(item.metadata["source_authority"] == "confirmed_user_record" for item in contract.evidence_refs)
    assert all(item.metadata["stated_role"] == "" for item in contract.evidence_refs)
    assert "Grounded profile" not in str(context.available_evidence)
    assert all(item.source_type != "candidate_preference" for item in context.available_evidence)


def test_unknown_relationship_cannot_prepare_cv(repo):
    service = search_service(repo, RelationshipClient(unknown=True))
    service.analyze_pending("a", limit=1)
    assert not ApplicationContractService().build("a", job().id).eligible
    with pytest.raises(ValueError, match="not eligible"):
        ApplicationContextService().build("a", job().id)


def test_changed_confirmed_source_requires_reanalysis_before_cv(repo):
    service = search_service(repo, RelationshipClient())
    service.analyze_pending("a", limit=1)
    onboarding = repo.get_onboarding("a")
    onboarding.desired_next_work = "Changed direction"
    repo.save_onboarding(onboarding)
    with pytest.raises(ValueError, match="reanalysis"):
        ApplicationContractService().build("a", job().id)
