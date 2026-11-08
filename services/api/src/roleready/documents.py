from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

from docx import Document
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from roleready.schemas import ServiceError


def extract_text(filename: str, content: bytes) -> str:
    if not content or len(content) > 5 * 1024 * 1024:
        raise ServiceError("file_size", "Choose a non-empty file smaller than 5 MB.", 413)
    extension = Path(filename).suffix.lower()
    try:
        if extension == ".txt":
            text = content.decode("utf-8-sig")
        elif extension == ".pdf":
            pdf = PdfReader(BytesIO(content))
            if pdf.is_encrypted or len(pdf.pages) > 20:
                raise ServiceError("pdf_limit", "Use an unencrypted PDF of 20 pages or fewer.", 422)
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        elif extension == ".docx":
            with ZipFile(BytesIO(content)) as archive:
                if sum(f.file_size for f in archive.infolist()) > 25 * 1024 * 1024:
                    raise ServiceError("document_limit", "This document is too large when expanded.", 413)
            doc = Document(BytesIO(content))
            text = "\n".join(
                [p.text for p in doc.paragraphs]
                + [c.text for t in doc.tables for r in t.rows for c in r.cells]
            )
        else:
            raise ServiceError("file_type", "Upload a PDF, DOCX or UTF-8 TXT file.", 415)
    except ServiceError:
        raise
    except (Exception,) as exc:
        # Parser details may contain document text. Do not expose/log them.
        raise ServiceError(
            "unreadable_document", "The document could not be read. Try pasting its text instead.", 422
        ) from exc
    text = text.strip()
    if len(text) < 40:
        raise ServiceError(
            "no_text",
            "No usable text was found. Scanned PDFs need OCR first; you can paste the CV text.",
            422,
        )
    if len(text) > 24000:
        raise ServiceError(
            "text_limit", "The extracted text exceeds 24,000 characters. Paste a shorter CV.", 422
        )
    return text


def build_report(session: dict) -> dict:
    questions, answers = session["analysis"]["questions"], session["answers"]
    if any(q["id"] not in answers for q in questions):
        raise ServiceError(
            "incomplete_session", "Answer and score all seven questions before creating the cheat sheet.", 409
        )
    items = [
        {
            "question_id": q["id"],
            "question": q["text"],
            "skill": q["skill"],
            "score": answers[q["id"]]["evaluation"]["score"],
            "feedback": answers[q["id"]]["evaluation"]["feedback"],
            "practice_points": q["reference_criteria"],
            "reference_answer": q["reference_answer"],
        }
        for q in questions
    ]
    priority = sorted(items, key=lambda item: item["score"])[:3]
    return {
        "role": session["inputs"]["role"],
        "average_score": round(sum(i["score"] for i in items) / 7, 2),
        "rubric_version": "interview-v1",
        "items": items,
        "priorities": [i["question_id"] for i in priority],
        "notice": "Practice feedback, not a hiring prediction. Scores are provisional and need human calibration. Reference answers are guidance; use your own real experience.",
    }


def render_pdf(report: dict) -> bytes:
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#174f45")
    styles["BodyText"].leading = 15
    story = []

    def add(text, style="BodyText"):
        story.append(Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style]))
        story.append(Spacer(1, 8))

    add("RoleReady | Interview cheat sheet", "Title")
    add(report["role"], "Heading2")
    add(f"Practice score: {report['average_score']}/5 | Rubric: {report['rubric_version']}")
    add(report["notice"])
    add("Focus next: " + ", ".join(report["priorities"]))
    for i, item in enumerate(report["items"], 1):
        add(f"{i}. {item['skill']} — {item['score']}/5", "Heading2")
        add(item["question"], "Heading3")
        add(item["feedback"])
        add("Practice checklist", "Heading3")
        for point in item["practice_points"]:
            add("• " + point)
        add("Reference guidance: " + item["reference_answer"])
    SimpleDocTemplate(
        buffer,
        title="RoleReady interview cheat sheet",
        author="RoleReady",
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    ).build(story)
    return buffer.getvalue()
