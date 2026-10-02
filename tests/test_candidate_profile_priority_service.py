from copy import deepcopy
from dataclasses import asdict
from unittest.mock import Mock

import pytest

from models.candidate import Candidate
from models.candidate_priority import CandidatePriority
from services.candidate_profile_priority_service import (
    CandidateProfilePriorityNotFoundError,
    CandidateProfilePriorityService,
)
from services.candidate_repository import CandidateRepository


@pytest.fixture
def candidate():
    return Candidate(id="a", name="Fixture", current_role="Support", current_level="Senior",
                     professional_summary="Source unchanged", skills=["Tool"],
                     strengths=["Strength"], target_roles=["Operations"],
                     priorities=[CandidatePriority("First"), CandidatePriority("Second", "negative", False)])


def test_list_is_ordered_and_detached(candidate):
    repository = Mock()
    repository.get.return_value = candidate
    service = CandidateProfilePriorityService(repository)
    result = service.list("a")
    assert result == tuple(candidate.priorities)
    assert isinstance(result, tuple)
    result[0].text = "UI mutation"
    assert candidate.priorities[0].text == "First"
    repository.get.assert_called_once_with("a")
    repository.save.assert_not_called()


def test_crud_preserves_all_unrelated_fields_order_and_candidate_scope(candidate):
    repository = CandidateRepository()
    repository.save(candidate)
    other = deepcopy(candidate)
    other.id = "b"
    repository.save(other)
    original = asdict(repository.get("a"))
    original.pop("priorities")
    service = CandidateProfilePriorityService(repository)

    def verify(expected):
        stored = repository.get("a")
        assert stored.priorities == expected
        fields = asdict(stored)
        fields.pop("priorities")
        assert fields == original
        assert repository.get("b") == other

    added = service.add("a", "  Third  ", direction="negative", active=False)
    assert added == CandidatePriority("Third", "negative", False)
    verify([*candidate.priorities, added])
    updated = service.update("a", 1, text=" Changed ", direction="positive", active=True)
    assert updated == CandidatePriority("Changed")
    verify([candidate.priorities[0], updated, added])
    removed = service.remove("a", 0)
    assert removed == candidate.priorities[0]
    verify([updated, added])


@pytest.mark.parametrize("operation", ["list", "add", "update", "remove"])
def test_missing_candidate_never_creates_one(operation):
    repository = Mock()
    repository.get.return_value = None
    service = CandidateProfilePriorityService(repository)
    with pytest.raises(CandidateProfilePriorityNotFoundError):
        if operation == "list":
            service.list("missing")
        elif operation == "add":
            service.add("missing", "Text")
        elif operation == "update":
            service.update("missing", 0, text="Text", direction="positive", active=True)
        else:
            service.remove("missing", 0)
    repository.save.assert_not_called()


@pytest.mark.parametrize("operation", ["add", "update"])
@pytest.mark.parametrize("values", [
    {"text": ""}, {"text": " \n\t "}, {"direction": "unsupported"}, {"active": "false"},
])
def test_invalid_priority_does_not_mutate_or_save(candidate, operation, values):
    repository = Mock()
    repository.get.return_value = candidate
    before = deepcopy(candidate)
    service = CandidateProfilePriorityService(repository)
    kwargs = dict(text="Valid", direction="positive", active=True)
    kwargs.update(values)
    with pytest.raises(ValueError):
        if operation == "add":
            service.add("a", **kwargs)
        else:
            service.update("a", 0, **kwargs)
    assert candidate == before
    repository.save.assert_not_called()


@pytest.mark.parametrize("operation", ["update", "remove"])
@pytest.mark.parametrize("index", [-1, 2, True])
def test_invalid_index_does_not_mutate_or_save(candidate, operation, index):
    repository = Mock()
    repository.get.return_value = candidate
    before = deepcopy(candidate)
    service = CandidateProfilePriorityService(repository)
    with pytest.raises(IndexError):
        if operation == "update":
            service.update("a", index, text="New", direction="positive", active=True)
        else:
            service.remove("a", index)
    assert candidate == before
    repository.save.assert_not_called()
