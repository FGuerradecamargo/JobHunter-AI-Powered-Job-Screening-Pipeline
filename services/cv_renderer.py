from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt


def _set_default_font(document: Document) -> None:
    styles = document.styles

    normal_style = styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(10)

    for style_name in [
        "Title",
        "Heading 1",
        "Heading 2",
    ]:
        style = styles[style_name]
        style.font.name = "Arial"


def _add_bullet(
    document: Document,
    text: str,
) -> None:
    paragraph = document.add_paragraph(
        style="List Bullet"
    )
    paragraph.add_run(text)


def render_tailored_cv_docx(
    candidate_name: str,
    tailored_cv: dict,
) -> bytes:
    document = Document()

    _set_default_font(document)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    run = title.add_run(candidate_name)
    run.bold = True
    run.font.size = Pt(18)

    headline = tailored_cv.get(
        "headline",
        "",
    )

    if headline:
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

        run = paragraph.add_run(headline)
        run.bold = True
        run.font.size = Pt(11)

    professional_summary = tailored_cv.get(
        "professional_summary",
        "",
    )

    if professional_summary:
        document.add_heading(
            "Professional Summary",
            level=1,
        )
        document.add_paragraph(
            professional_summary
        )

    key_skills = tailored_cv.get(
        "key_skills",
        [],
    )

    if key_skills:
        document.add_heading(
            "Key Skills",
            level=1,
        )
        document.add_paragraph(
            " | ".join(key_skills)
        )

    experiences = tailored_cv.get(
        "experiences",
        [],
    )

    if experiences:
        document.add_heading(
            "Professional Experience",
            level=1,
        )

        for experience in experiences:
            role = experience.get(
                "role",
                "",
            )

            company = experience.get(
                "company",
                "",
            )

            heading_parts = [
                value
                for value in [
                    role,
                    company,
                ]
                if value
            ]

            if heading_parts:
                paragraph = document.add_paragraph()

                run = paragraph.add_run(
                    " - ".join(heading_parts)
                )
                run.bold = True

            bullets = experience.get(
                "tailored_bullets",
                [],
            )

            for bullet in bullets:
                _add_bullet(
                    document,
                    bullet,
                )

    additional_information = tailored_cv.get(
        "additional_relevant_information",
        [],
    )

    if additional_information:
        document.add_heading(
            "Additional Relevant Information",
            level=1,
        )

        for item in additional_information:
            _add_bullet(
                document,
                item,
            )

    buffer = BytesIO()
    document.save(buffer)

    return buffer.getvalue()
