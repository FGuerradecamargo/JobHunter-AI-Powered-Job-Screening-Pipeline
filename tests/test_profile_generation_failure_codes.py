from unittest.mock import Mock

import pytest

from services.career_update_repository import (
    CareerUpdateRepository,
)
from services.profile_generation_failure import (
    ProfileGenerationFailure,
)
from services.profile_interpretation_service import (
    ProfileInterpretationService,
)
from services.profile_snapshot_repository import (
    ProfileSnapshotRepository,
)
from services.provider_failure import (
    failure_code,
)
from tests.test_v1_runtime_candidate_profile import (
    Client,
    service,
)
from tests.test_workpilot_v1_onboarding_persistence import (
    repo,
)


def test_profile_failure_code_is_safe_and_allowlisted():
    error = ProfileGenerationFailure(
        "invalid_json"
    )

    assert (
        error.code
        == "invalid_json"
    )

    assert (
        failure_code(error)
        == "invalid_json"
    )

    assert (
        str(error)
        == "Invalid structured candidate interpretation."
    )


def test_invalid_raw_json_has_specific_safe_code(
    repo,
):
    class InvalidClient:
        def generate(
            self,
            prompt,
        ):
            return "not-json"

    generator = service(
        repo,
        InvalidClient(),
    )

    with pytest.raises(
        ProfileGenerationFailure
    ) as caught:
        generator.generate(
            "a",
            "Fixture",
        )

    assert (
        caught.value.code
        == "invalid_json"
    )


def test_domain_validation_failure_has_specific_safe_code(
    repo,
):
    generator = service(
        repo,
        Client(
            preference_as_skill=True
        ),
    )

    with pytest.raises(
        ProfileGenerationFailure
    ) as caught:
        generator.generate(
            "a",
            "Fixture",
        )

    assert (
        caught.value.code
        == "invalid_structured_output"
    )


def test_missing_professional_evidence_has_specific_safe_code(
    repo,
):
    interpreter = Mock()

    service_under_test = (
        ProfileInterpretationService(
            ProfileSnapshotRepository(),
            interpreter,
        )
    )

    with pytest.raises(
        ProfileGenerationFailure
    ) as caught:
        (
            service_under_test
            .candidate_profile_from_onboarding(
                candidate_id="b",
                onboarding_repository=repo,
                career_update_repository=(
                    CareerUpdateRepository()
                ),
            )
        )

    assert (
        caught.value.code
        == "no_professional_evidence"
    )

    interpreter.build_candidate_profile.assert_not_called()


def test_profile_interpretation_source_contains_safe_guard_codes():
    from pathlib import Path

    source = Path(
        "services/profile_interpretation_service.py"
    ).read_text(
        encoding="utf-8"
    )

    for code in (
        "no_professional_evidence",
        "narrative_coverage_guard",
        "capability_evidence_guard",
        "snapshot_persistence_failed",
    ):
        assert (
            f'"{code}"'
            in source
        )
