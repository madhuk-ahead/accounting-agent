#!/usr/bin/env python3
"""Generate sample_invoice.jpg using Pillow (no cairosvg required)."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_PATH = PROJECT_ROOT / "frontend" / "static" / "sample_invoice.jpg"


def main() -> None:
    from PIL import Image, ImageDraw, ImageFont

    w, h = 600, 780
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_lg = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_md = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 11)
    except OSError:
        font_lg = ImageFont.load_default()
        font_md = font_lg
        font_sm = font_lg

    # Colors
    dark = (30, 41, 59)
    gray = (100, 116, 139)
    light_gray = (148, 163, 184)

    # From (left)
    draw.text((40, 40), "FROM", fill=gray, font=font_sm)
    draw.text((40, 58), "TechSupply Inc.", fill=dark, font=font_md)
    draw.text((40, 76), "123 Commerce St", fill=dark, font=font_md)
    draw.text((40, 94), "San Francisco, CA 94105", fill=dark, font=font_md)

    # Invoice # (right)
    draw.text((380, 40), "INVOICE #", fill=gray, font=font_sm)
    draw.text((380, 58), "INV-2026-001", fill=dark, font=font_md)
    draw.text((380, 96), "DATE", fill=gray, font=font_sm)
    draw.text((380, 114), "2026-02-28", fill=dark, font=font_md)
    draw.text((380, 146), "DUE DATE", fill=gray, font=font_sm)
    draw.text((380, 164), "2026-03-30", fill=dark, font=font_md)
    draw.text((380, 196), "PO REFERENCE", fill=gray, font=font_sm)
    draw.text((380, 214), "PO-5001", fill=dark, font=font_md)

    # Invoice title
    draw.text((40, 268), "Invoice", fill=dark, font=font_lg)
    draw.line([(40, 298), (560, 298)], fill=(226, 232, 240))

    # Table header
    draw.text((40, 318), "Description", fill=gray, font=font_sm)
    draw.text((420, 318), "Amount", fill=gray, font=font_sm)
    draw.line([(40, 335), (560, 335)], fill=(226, 232, 240))

    # Line items
    draw.text((40, 352), "IT Equipment (Laptops)", fill=dark, font=font_md)
    draw.text((480, 352), "$3,200.00", fill=dark, font=font_md)
    draw.text((40, 378), "Software License (Annual)", fill=dark, font=font_md)
    draw.text((480, 378), "$1,300.00", fill=dark, font=font_md)
    draw.line([(40, 415), (560, 415)], fill=(226, 232, 240))

    # Totals
    draw.text((40, 438), "Subtotal", fill=dark, font=font_md)
    draw.text((480, 438), "$4,500.00", fill=dark, font=font_md)
    draw.text((40, 462), "Tax", fill=dark, font=font_md)
    draw.text((480, 462), "$360.00", fill=dark, font=font_md)
    draw.text((40, 500), "Total", fill=dark, font=font_lg)
    draw.text((480, 500), "$4,860.00 USD", fill=dark, font=font_lg)

    # Payment terms
    draw.text((40, 555), "Payment terms", fill=gray, font=font_sm)
    draw.text((40, 573), "Net 30", fill=dark, font=font_md)

    # Remit to
    draw.text((40, 625), "Remit to", fill=gray, font=font_sm)
    draw.text((40, 643), "TechSupply Inc.", fill=dark, font=font_md)
    draw.text((40, 661), "123 Commerce St", fill=dark, font=font_md)
    draw.text((40, 679), "San Francisco, CA 94105", fill=dark, font=font_md)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT_PATH, "JPEG", quality=92)
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
