#!/usr/bin/env python3
"""
Generate sample invoice as PDF and image (PNG) for AP Invoice Triage demo.

Usage:
  python scripts/generate_sample_invoice.py [--output-dir DIR]

Outputs:
  - sample_invoice.pdf
  - sample_invoice.png (requires cairosvg: pip install cairosvg)

Without cairosvg, only the PDF is generated.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SVG_PATH = REPO_ROOT / "frontend" / "static" / "sample_invoice.svg"


def generate_pdf(output_path: Path) -> None:
    """Create sample invoice PDF using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        print("Install reportlab: pip install reportlab")
        raise

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=24,
        spaceAfter=20,
    )
    elements.append(Paragraph("Invoice", title_style))
    elements.append(Spacer(1, 0.2 * inch))

    # From / Vendor (left)
    elements.append(Paragraph("<b>From</b>", styles["Normal"]))
    elements.append(Paragraph("TechSupply Inc.", styles["Normal"]))
    elements.append(Paragraph("123 Commerce St", styles["Normal"]))
    elements.append(Paragraph("San Francisco, CA 94105", styles["Normal"]))
    elements.append(Spacer(1, 0.15 * inch))

    # Invoice #, Date, Due Date, PO Reference
    inv_data = [
        ["Invoice #", "INV-2026-001"],
        ["Date", "2026-02-28"],
        ["Due Date", "2026-03-30"],
        ["PO Reference", "PO-5001"],
    ]
    inv_table = Table(inv_data, colWidths=[2 * inch, 3 * inch])
    inv_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(inv_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Line items table
    line_data = [
        ["Description", "Amount"],
        ["IT Equipment (Laptops)", "$3,200.00"],
        ["Software License (Annual)", "$1,300.00"],
        ["Subtotal", "$4,500.00"],
        ["Tax", "$360.00"],
        ["Total", "$4,860.00 USD"],
    ]
    line_table = Table(line_data, colWidths=[4.5 * inch, 1.5 * inch])
    line_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.grey),
        ("LINEABOVE", (0, -1), (-1, -1), 2, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Payment terms & Remit to
    elements.append(Paragraph("<b>Payment terms</b>", styles["Normal"]))
    elements.append(Paragraph("Net 30", styles["Normal"]))
    elements.append(Spacer(1, 0.15 * inch))
    elements.append(Paragraph("<b>Remit to</b>", styles["Normal"]))
    elements.append(Paragraph("TechSupply Inc.", styles["Normal"]))
    elements.append(Paragraph("123 Commerce St", styles["Normal"]))
    elements.append(Paragraph("San Francisco, CA 94105", styles["Normal"]))

    doc.build(elements)
    print(f"Generated: {output_path}")


def generate_png(output_path: Path) -> bool:
    """Convert existing SVG to PNG using cairosvg. Returns True if successful."""
    if not SVG_PATH.exists():
        print(f"SVG not found: {SVG_PATH}")
        return False
    try:
        import cairosvg
        cairosvg.svg2png(
            url=str(SVG_PATH),
            write_to=str(output_path),
            output_width=1200,
            output_height=1560,
            dpi=150,
        )
        print(f"Generated: {output_path}")
        return True
    except ImportError:
        print("Skipping PNG (install cairosvg for image output: pip install cairosvg)")
        return False
    except Exception as e:
        print(f"PNG generation failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample invoice PDF and PNG")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=REPO_ROOT / "frontend" / "static",
        help="Directory for output files (default: frontend/static)",
    )
    args = parser.parse_args()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = out_dir / "sample_invoice.pdf"
    png_path = out_dir / "sample_invoice.png"

    generate_pdf(pdf_path)
    if not generate_png(png_path):
        sys.exit(0)  # PDF success is enough
    print("Done. Use sample_invoice.pdf or sample_invoice.png for demo uploads.")


if __name__ == "__main__":
    main()
