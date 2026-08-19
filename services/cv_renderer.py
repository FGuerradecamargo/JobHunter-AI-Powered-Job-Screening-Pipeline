from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


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

def render_tailored_cv_pdf(
    candidate_name: str,
    tailored_cv: dict,
) -> bytes:
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CVTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    headline_style = ParagraphStyle(
        "CVHeadline",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    heading_style = ParagraphStyle(
        "CVHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceBefore=8,
        spaceAfter=5,
    )

    body_style = ParagraphStyle(
        "CVBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        spaceAfter=6,
    )

    role_style = ParagraphStyle(
        "CVRole",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        spaceBefore=5,
        spaceAfter=3,
    )

    story = []

    story.append(
        Paragraph(
            candidate_name,
            title_style,
        )
    )

    headline = tailored_cv.get(
        "headline",
        "",
    )

    if headline:
        story.append(
            Paragraph(
                headline,
                headline_style,
            )
        )

    professional_summary = tailored_cv.get(
        "professional_summary",
        "",
    )

    if professional_summary:
        story.append(
            Paragraph(
                "Professional Summary",
                heading_style,
            )
        )

        story.append(
            Paragraph(
                professional_summary,
                body_style,
            )
        )

    key_skills = tailored_cv.get(
        "key_skills",
        [],
    )

    if key_skills:
        story.append(
            Paragraph(
                "Key Skills",
                heading_style,
            )
        )

        story.append(
            Paragraph(
                " | ".join(key_skills),
                body_style,
            )
        )

    experiences = tailored_cv.get(
        "experiences",
        [],
    )

    if experiences:
        story.append(
            Paragraph(
                "Professional Experience",
                heading_style,
            )
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
                story.append(
                    Paragraph(
                        " - ".join(heading_parts),
                        role_style,
                    )
                )

            bullets = experience.get(
                "tailored_bullets",
                [],
            )

            if bullets:
                bullet_items = [
                    ListItem(
                        Paragraph(
                            bullet,
                            body_style,
                        )
                    )
                    for bullet in bullets
                ]

                story.append(
                    ListFlowable(
                        bullet_items,
                        bulletType="bullet",
                        leftIndent=14,
                    )
                )

                story.append(
                    Spacer(
                        1,
                        4,
                    )
                )

    additional_information = tailored_cv.get(
        "additional_relevant_information",
        [],
    )

    if additional_information:
        story.append(
            Paragraph(
                "Additional Relevant Information",
                heading_style,
            )
        )

        bullet_items = [
            ListItem(
                Paragraph(
                    item,
                    body_style,
                )
            )
            for item in additional_information
        ]

        story.append(
            ListFlowable(
                bullet_items,
                bulletType="bullet",
                leftIndent=14,
            )
        )

    document.build(story)

    return buffer.getvalue()

