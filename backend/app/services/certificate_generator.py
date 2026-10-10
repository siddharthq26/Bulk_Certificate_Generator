"""
Certificate PDF Generator using ReportLab.

Generates a styled A4 landscape PDF certificate with:
  - Decorative border
  - Organization logo placeholder
  - Recipient name in large font
  - Event/course name
  - Issued by
  - Completion date
  - Unique certificate ID
"""
import os
import uuid
from datetime import datetime, UTC
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER

from app.core.config import settings


# ─── Color palette ────────────────────────────────────────────────────────────
GOLD = colors.HexColor("#C9A84C")
DARK_BLUE = colors.HexColor("#1B3A6B")
LIGHT_BLUE = colors.HexColor("#EAF0FB")
WHITE = colors.white
GRAY = colors.HexColor("#555555")


def _ensure_storage_dir() -> Path:
    path = Path(settings.CERT_STORAGE_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_certificate(
    recipient_name: str,
    recipient_email: str,
    event_name: str,
    issued_by: str,
    course_name: str | None = None,
    completion_date: str | None = None,
    certificate_id: str | None = None,
) -> str:
    """
    Generate a PDF certificate and return the absolute file path.

    Args:
        recipient_name:   Full name of the recipient
        recipient_email:  Email address (used in filename)
        event_name:       Name of the event or program
        issued_by:        Issuing organization name
        course_name:      Optional course/module name
        completion_date:  ISO date string (YYYY-MM-DD) or None
        certificate_id:   Unique ID; auto-generated if not provided

    Returns:
        Absolute path to the generated PDF file.

    Raises:
        Exception: Any error during PDF creation propagates to the caller.
    """
    storage_dir = _ensure_storage_dir()
    cert_id = certificate_id or str(uuid.uuid4())

    # Sanitize email for filename
    safe_email = "".join(c if c.isalnum() or c in "-_." else "_" for c in recipient_email)
    filename = f"certificate_{safe_email}_{cert_id[:8]}.pdf"
    filepath = storage_dir / filename

    # Canvas — A4 landscape
    page_w, page_h = landscape(A4)  # 841.89 x 595.28 pts
    c = canvas.Canvas(str(filepath), pagesize=landscape(A4))

    # ── Background ────────────────────────────────────────────────────────────
    c.setFillColor(LIGHT_BLUE)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # ── Outer gold border ─────────────────────────────────────────────────────
    margin = 18
    border_w = 6
    c.setStrokeColor(GOLD)
    c.setLineWidth(border_w)
    c.rect(margin, margin, page_w - 2 * margin, page_h - 2 * margin, fill=0, stroke=1)

    # ── Inner thin dark-blue border ───────────────────────────────────────────
    inner_margin = margin + border_w + 4
    c.setStrokeColor(DARK_BLUE)
    c.setLineWidth(1.5)
    c.rect(inner_margin, inner_margin, page_w - 2 * inner_margin, page_h - 2 * inner_margin, fill=0, stroke=1)

    # ── Header bar ────────────────────────────────────────────────────────────
    header_h = 70
    c.setFillColor(DARK_BLUE)
    c.rect(inner_margin, page_h - inner_margin - header_h,
           page_w - 2 * inner_margin, header_h, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(page_w / 2, page_h - inner_margin - 44, "CERTIFICATE OF COMPLETION")

    # ── "This certifies that" label ───────────────────────────────────────────
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(page_w / 2, page_h - inner_margin - header_h - 30, "This is to certify that")

    # ── Recipient Name ────────────────────────────────────────────────────────
    c.setFillColor(DARK_BLUE)
    c.setFont("Helvetica-Bold", 40)
    c.drawCentredString(page_w / 2, page_h - inner_margin - header_h - 75, recipient_name)

    # Decorative underline beneath name
    name_y = page_h - inner_margin - header_h - 82
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(page_w / 2 - 160, name_y, page_w / 2 + 160, name_y)

    # ── "has successfully completed" ──────────────────────────────────────────
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 14)
    c.drawCentredString(page_w / 2, page_h - inner_margin - header_h - 110,
                        "has successfully completed")

    # ── Event / Course Name ───────────────────────────────────────────────────
    display_course = course_name or event_name
    c.setFillColor(DARK_BLUE)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(page_w / 2, page_h - inner_margin - header_h - 145, display_course)

    # ── Issued by ─────────────────────────────────────────────────────────────
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 12)
    c.drawCentredString(page_w / 2, page_h - inner_margin - header_h - 180,
                        f"Issued by: {issued_by}")

    # ── Completion date ───────────────────────────────────────────────────────
    if completion_date:
        try:
            dt = datetime.strptime(completion_date, "%Y-%m-%d")
            formatted_date = dt.strftime("%B %d, %Y")
        except ValueError:
            formatted_date = completion_date
    else:
        formatted_date = datetime.now(UTC).strftime("%B %d, %Y")

    c.drawCentredString(page_w / 2, page_h - inner_margin - header_h - 205,
                        f"Date: {formatted_date}")

    # ── Signature line (left) ─────────────────────────────────────────────────
    sig_y = inner_margin + 55
    c.setStrokeColor(DARK_BLUE)
    c.setLineWidth(1)
    c.line(80, sig_y, 230, sig_y)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 10)
    c.drawCentredString(155, sig_y - 15, "Authorized Signature")

    # ── Signature line (right) ────────────────────────────────────────────────
    c.line(page_w - 230, sig_y, page_w - 80, sig_y)
    c.drawCentredString(page_w - 155, sig_y - 15, "Director / Organizer")

    # ── Certificate ID watermark ──────────────────────────────────────────────
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 8)
    c.drawCentredString(page_w / 2, inner_margin + 10,
                        f"Certificate ID: {cert_id} | Verify at: https://certs.example.com/verify/{cert_id}")

    c.save()
    return str(filepath)
