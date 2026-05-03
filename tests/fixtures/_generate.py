"""Deterministic PDF fixtures for Docling integration tests."""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _register_unicode_font() -> str:
    candidates = [
        Path("/Library/Fonts/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ]
    for font_path in candidates:
        if font_path.is_file():
            pdfmetrics.registerFont(TTFont("BigosUnicode", str(font_path)))
            return "BigosUnicode"
    return "Helvetica"


def write_simple_text_pdf(dest: Path) -> None:
    """Vector text with a clear vertical gap so layout yields two body paragraphs."""
    c = canvas.Canvas(str(dest), pagesize=letter)
    _w, h = letter
    y = h - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, "Introduction")
    y -= 48
    c.setFont("Helvetica", 11)
    c.drawString(
        72,
        y,
        "First paragraph describes the purpose of this sample document.",
    )
    y -= 120
    c.drawString(
        72,
        y,
        "Second paragraph adds more detail for Docling layout extraction.",
    )
    c.save()


def write_with_table_pdf(dest: Path) -> None:
    """Draw explicit grid lines + cell text for Docling table structure detection."""
    c = canvas.Canvas(str(dest), pagesize=letter)
    _w, h = letter
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, h - 72, "Report with grid")
    x0, y0 = 72, h - 160
    cell_w, cell_h = 100, 36
    rows, cols = 3, 3
    for i in range(cols + 1):
        xi = x0 + i * cell_w
        c.line(xi, y0, xi, y0 - rows * cell_h)
    for j in range(rows + 1):
        yj = y0 - j * cell_h
        c.line(x0, yj, x0 + cols * cell_w, yj)
    c.setFont("Helvetica", 10)
    for r in range(rows):
        for col in range(cols):
            tx = x0 + 6 + col * cell_w
            ty = y0 - 22 - r * cell_h
            c.drawString(tx, ty, f"R{r}C{col}")
    c.save()


def write_polish_pdf(dest: Path, font_name: str) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="PlTitle",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=14,
        leading=18,
    )
    body = ParagraphStyle(
        name="PlBody",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=11,
        leading=14,
    )
    text = "Zażółć gęślą jaźń. Polskie znaki diakrytyczne: ąęćłńóśźż."
    doc = SimpleDocTemplate(str(dest), pagesize=letter)
    story = [
        Paragraph("Nagłówek po polsku", title_style),
        Spacer(1, 0.2 * inch),
        Paragraph(text, body),
    ]
    doc.build(story)


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    font_name = _register_unicode_font()
    write_simple_text_pdf(out_dir / "simple_text.pdf")
    write_with_table_pdf(out_dir / "with_table.pdf")
    write_polish_pdf(out_dir / "polish.pdf", font_name)
    print(f"Wrote PDF fixtures under {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
