from io import BytesIO
from pathlib import Path

from docx import Document
import pytest

from models.prepare_application import PrepareApplicationResult
from models.tailored_cv_contract import (
    DraftTailoredCV,
    DraftTailoredCVExperience,
    TailoredCVStatement,
)
from services.ai.tailored_cv_generator_adapter import TailoredCVGeneratorAdapter
from services.prepare_application_factory import build_prepare_application_service
from services.prepared_application_ui import (
    handle_prepare_application_action,
    prepared_application_state_key,
)
from services.prepared_cv_exporter import (
    DOCX_MIME_TYPE,
    build_prepared_cv_filename,
    export_cached_prepared_cv_docx,
    export_prepared_cv_docx,
)
from services.tailored_cv_generator_client import TailoredCVGeneratorClient


def _statement(text, claim_type="summary"):
    return TailoredCVStatement(
        text=text,
        claim_type=claim_type,
        evidence_refs=["internal-evidence-ref"],
    )


def _result():
    cv = DraftTailoredCV(
        candidate_id="internal-candidate-id",
        job_id="internal-job-id",
        application_context_signature="internal-context-signature",
        headline=_statement("Product Operations Specialist"),
        professional_summary=[
            _statement("Evidence-led operations professional")
        ],
        key_skills=[_statement("SQL", "skill")],
        experiences=[
            DraftTailoredCVExperience(
                source_experience_id="internal-experience-id",
                company="Example Ltd",
                role="Operations Specialist",
                bullets=[
                    _statement(
                        "Improved support processes",
                        "professional_experience",
                    )
                ],
            )
        ],
        additional_relevant_information=[
            _statement("Stakeholder communication", "transferable_capability")
        ],
    )
    return PrepareApplicationResult(
        status="prepared",
        candidate_id="internal-candidate-id",
        job_id="internal-job-id",
        analysis_id="internal-analysis-id",
        application_context_signature="internal-context-signature",
        cv=cv,
        generation_status="validated",
    )


def _export():
    return export_prepared_cv_docx(
        _result(),
        candidate_name="Felipe Camargo",
        company="Target Ltd",
        role="Product Operations Specialist",
    )


def _document_text(data):
    document = Document(BytesIO(data))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def test_validated_cv_exports_as_docx_bytes():
    exported = _export()

    assert exported.data.startswith(b"PK")
    assert exported.mime_type == DOCX_MIME_TYPE
    assert exported.filename.endswith(".docx")


@pytest.mark.parametrize(
    "expected",
    [
        "Product Operations Specialist",
        "Evidence-led operations professional",
        "SQL",
        "Example Ltd | Operations Specialist",
        "Improved support processes",
        "Stakeholder communication",
    ],
)
def test_export_contains_each_presentation_section(expected):
    assert expected in _document_text(_export().data)


@pytest.mark.parametrize(
    "internal_value",
    [
        "internal-evidence-ref",
        "professional_experience",
        "transferable_capability",
        "internal-experience-id",
        "internal-context-signature",
        "internal-analysis-id",
        "tailored-cv-v1",
    ],
)
def test_export_excludes_provenance_and_internal_metadata(internal_value):
    assert internal_value not in _document_text(_export().data)


def test_filename_sanitizes_reserved_characters_without_internal_ids():
    filename = build_prepared_cv_filename(
        candidate_name='First/Name\\Test',
        company='Target:*?"Company',
        role="Ops<Lead>|EU",
    )

    assert filename == "First_Name_Test_Target_Company_Ops_Lead_EU_CV.docx"
    assert not any(character in filename for character in '/\\:*?"<>|')
    assert "internal" not in filename


def test_docx_export_is_byte_deterministic():
    assert _export().data == _export().data


def test_unvalidated_result_cannot_be_exported():
    result = PrepareApplicationResult(
        status="generation_failed",
        candidate_id="internal-candidate-id",
        job_id="internal-job-id",
        cv=_result().cv,
    )

    with pytest.raises(ValueError, match="validated prepared CV"):
        export_prepared_cv_docx(
            result,
            candidate_name="Candidate",
            company="Company",
            role="Role",
        )


class FakePreparationService:
    def __init__(self):
        self.calls = []

    def prepare(self, candidate_id, job_id):
        self.calls.append((candidate_id, job_id))
        return _result()


def test_cached_download_and_rerender_do_not_regenerate():
    state = {}
    service = FakePreparationService()
    handle_prepare_application_action(
        state,
        candidate_id="internal-candidate-id",
        job_id="internal-job-id",
        analysis={"recommendation": "best_match"},
        action_requested=True,
        preparation_service=service,
    )
    handle_prepare_application_action(
        state,
        candidate_id="internal-candidate-id",
        job_id="internal-job-id",
        analysis={"recommendation": "best_match"},
        action_requested=False,
        preparation_service=service,
    )
    first = export_cached_prepared_cv_docx(
        state,
        candidate_id="internal-candidate-id",
        job_id="internal-job-id",
        candidate_name="Candidate",
        company="Company",
        role="Role",
    )
    second = export_cached_prepared_cv_docx(
        state,
        candidate_id="internal-candidate-id",
        job_id="internal-job-id",
        candidate_name="Candidate",
        company="Company",
        role="Role",
    )

    assert first.data == second.data
    assert service.calls == [("internal-candidate-id", "internal-job-id")]


def test_cached_export_is_candidate_and_job_scoped():
    state = {
        prepared_application_state_key(
            "internal-candidate-id",
            "internal-job-id",
        ): _result()
    }

    with pytest.raises(ValueError, match="not found"):
        export_cached_prepared_cv_docx(
            state,
            candidate_id="another-candidate",
            job_id="internal-job-id",
            candidate_name="Candidate",
            company="Company",
            role="Role",
        )


class NoCallLLMClient:
    def __init__(self):
        self.calls = []

    def generate(self, prompt):
        self.calls.append(prompt)
        raise AssertionError("No generation is allowed in this test.")


class FakeGeneratorAdapter:
    def generate(self, request):
        return "{}"


def test_adapter_construction_does_not_call_transport():
    transport = NoCallLLMClient()
    adapter = TailoredCVGeneratorAdapter(transport)

    assert isinstance(adapter, TailoredCVGeneratorClient)
    assert transport.calls == []


def test_fake_adapter_conforms_to_generator_protocol():
    assert isinstance(FakeGeneratorAdapter(), TailoredCVGeneratorClient)


def test_factory_construction_does_not_invoke_generator():
    generator = FakeGeneratorAdapter()
    service = build_prepare_application_service(generator_client=generator)

    assert service.generation_service.generator_client is generator


def test_adapter_module_does_not_import_openai_client():
    source = Path(
        "services/ai/tailored_cv_generator_adapter.py"
    ).read_text(encoding="utf-8")

    assert "OpenAIClient" not in source
    assert "from openai" not in source
    assert "responses.create" not in source


def test_export_does_not_mutate_preparation_or_application_state():
    result = _result()
    before = result
    state = {
        prepared_application_state_key(
            result.candidate_id,
            result.job_id,
        ): result,
        "opportunity_state": "in_review",
        "applied_at": None,
    }
    export_cached_prepared_cv_docx(
        state,
        candidate_id=result.candidate_id,
        job_id=result.job_id,
        candidate_name="Candidate",
        company="Company",
        role="Role",
    )

    assert result == before
    assert state["opportunity_state"] == "in_review"
    assert state["applied_at"] is None
