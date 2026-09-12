from io import BytesIO
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from models.prepare_application import PrepareApplicationResult
from models.prepared_cv_export import PreparedCVExport
from services.cv_renderer import render_tailored_cv_docx
from services.prepared_application_ui import build_prepared_cv_view
from services.prepared_application_ui import get_prepared_application


DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _filename_part(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', " ", str(value or ""))
    value = re.sub(r"\s+", "_", value.strip())
    value = re.sub(r"_+", "_", value)
    return value.strip("._")


def build_prepared_cv_filename(
    *,
    candidate_name: str,
    company: str,
    role: str,
) -> str:
    parts = [
        part
        for part in (
            _filename_part(candidate_name),
            _filename_part(company),
            _filename_part(role),
            "CV",
        )
        if part
    ]
    return "_".join(parts) + ".docx"


def _deterministic_docx(data: bytes) -> bytes:
    source = BytesIO(data)
    target = BytesIO()
    with ZipFile(source, "r") as archive, ZipFile(
        target,
        "w",
        compression=ZIP_DEFLATED,
        compresslevel=9,
    ) as output:
        for name in sorted(archive.namelist()):
            original = archive.getinfo(name)
            info = ZipInfo(name, _FIXED_ZIP_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = original.external_attr
            info.create_system = original.create_system
            output.writestr(info, archive.read(name))
    return target.getvalue()


def export_prepared_cv_docx(
    result: PrepareApplicationResult,
    *,
    candidate_name: str,
    company: str,
    role: str,
) -> PreparedCVExport:
    view = build_prepared_cv_view(result)
    if view is None:
        raise ValueError("A validated prepared CV is required for export.")
    presentation = {
        "headline": view.headline,
        "professional_summary": "\n\n".join(view.professional_summary),
        "key_skills": list(view.key_skills),
        "experiences": [
            {
                "company": item.company,
                "role": item.role,
                "tailored_bullets": list(item.bullets),
            }
            for item in view.experiences
        ],
        "additional_relevant_information": list(view.additional_information),
    }
    rendered = render_tailored_cv_docx(
        candidate_name=str(candidate_name or "").strip(),
        tailored_cv=presentation,
    )
    return PreparedCVExport(
        data=_deterministic_docx(rendered),
        filename=build_prepared_cv_filename(
            candidate_name=candidate_name,
            company=company,
            role=role,
        ),
        mime_type=DOCX_MIME_TYPE,
    )


def export_cached_prepared_cv_docx(
    session_state,
    *,
    candidate_id: str,
    job_id: str,
    candidate_name: str,
    company: str,
    role: str,
) -> PreparedCVExport:
    result = get_prepared_application(
        session_state,
        candidate_id=candidate_id,
        job_id=job_id,
    )
    if result is None:
        raise ValueError("Prepared CV was not found in this candidate session.")
    return export_prepared_cv_docx(
        result,
        candidate_name=candidate_name,
        company=company,
        role=role,
    )
