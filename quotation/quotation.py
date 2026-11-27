"""
quotation.py - Quotation Generator (AI Employee OS, module 10)

Two jobs:
  1. calculate_quotation(data) : checks the input and works out the totals.
  2. create_quotation_pdf(data, path) : writes a professional PDF quotation.

Both take a plain dictionary, so the backend or the website can call them
with JSON data. All percentages are decimals: 0.10 means 10%, 0.17 means 17%.

Calculation order:
  line amount     = quantity x unit price x (1 - item discount)
  subtotal        = sum of line amounts
  discount amount = subtotal x overall discount
  taxable amount  = subtotal - discount amount
  tax amount      = taxable amount x tax rate
  total           = taxable amount + tax amount

Money is calculated with Decimal and rounded half-up to 2 places, so results
do not drift the way plain floats can.

Run from the project folder:
  python quotation/quotation.py          run the checked examples
  python quotation/quotation.py sample   also write sample_quotation.pdf
"""

import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from xml.sax.saxutils import escape

TWO = Decimal("0.01")


# ---------------------------------------------------------------------------
# 1. CALCULATIONS
# ---------------------------------------------------------------------------

def _dec(value, name):
    try:
        return Decimal(str(value))
    except Exception:
        raise ValueError(f"{name} must be a number, got {value!r}")


def _money(value):
    return value.quantize(TWO, rounding=ROUND_HALF_UP)


def _rate(value, name):
    """A percentage given as a decimal, between 0 and 1."""
    rate = _dec(value, name)
    if rate < 0:
        raise ValueError(f"{name} cannot be negative")
    if rate > 1:
        raise ValueError(
            f"{name}={rate} looks like a percent number. "
            "Use a decimal instead (0.10 means 10%)."
        )
    return rate


def calculate_quotation(data):
    """Validate the input and return the line amounts and totals."""
    items = data.get("items") or []
    if not items:
        raise ValueError("a quotation needs at least one item")

    lines = []
    subtotal = Decimal("0")
    for i, item in enumerate(items, start=1):
        label = f"item {i}"
        description = str(item.get("description", "")).strip()
        if not description:
            raise ValueError(f"{label}: description is required")
        qty = _dec(item.get("quantity"), f"{label} quantity")
        price = _dec(item.get("unit_price"), f"{label} unit_price")
        discount = _rate(item.get("discount", 0), f"{label} discount")
        if qty <= 0:
            raise ValueError(f"{label}: quantity must be greater than 0")
        if price < 0:
            raise ValueError(f"{label}: unit_price cannot be negative")

        amount = _money(qty * price * (1 - discount))
        subtotal += amount
        lines.append({
            "description": description,
            "quantity": qty,
            "unit_price": _money(price),
            "discount": discount,
            "amount": amount,
        })

    discount_rate = _rate(data.get("discount", 0), "discount")
    tax_rate = _rate(data.get("tax_rate", 0), "tax_rate")

    discount_amount = _money(subtotal * discount_rate)
    taxable = subtotal - discount_amount
    tax_amount = _money(taxable * tax_rate)
    total = taxable + tax_amount

    return {
        "lines": [
            {**ln, "quantity": float(ln["quantity"]), "unit_price": float(ln["unit_price"]),
             "discount": float(ln["discount"]), "amount": float(ln["amount"])}
            for ln in lines
        ],
        "subtotal": float(subtotal),
        "discount_rate": float(discount_rate),
        "discount_amount": float(discount_amount),
        "taxable_amount": float(taxable),
        "tax_rate": float(tax_rate),
        "tax_amount": float(tax_amount),
        "total": float(total),
    }


# ---------------------------------------------------------------------------
# 2. PDF
# ---------------------------------------------------------------------------

def _fmt(value):
    return f"{value:,.2f}"


def _pct(rate):
    text = f"{rate * 100:.2f}".rstrip("0").rstrip(".")
    return text + "%"


def _qty(value):
    return f"{value:g}"


def create_quotation_pdf(data, output_path):
    """Write the quotation as a PDF. Returns the totals that were used."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle, KeepTogether)

    totals = calculate_quotation(data)
    company = data.get("company") or {}
    customer = data.get("customer") or {}
    currency = data.get("currency", "USD")

    quote_date = data.get("date") or date.today().isoformat()
    valid_until = data.get("valid_until")
    if not valid_until:
        valid_days = int(data.get("valid_days", 30))
        valid_until = (date.fromisoformat(str(quote_date)) + timedelta(days=valid_days)).isoformat()
    number = data.get("quotation_number", "DRAFT")

    base = getSampleStyleSheet()["Normal"]
    normal = ParagraphStyle("n", parent=base, fontName="Helvetica", fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=normal, fontSize=8.5, leading=11)
    bold = ParagraphStyle("b", parent=normal, fontName="Helvetica-Bold")
    right = ParagraphStyle("r", parent=normal, alignment=TA_RIGHT)
    right_bold = ParagraphStyle("rb", parent=right, fontName="Helvetica-Bold")
    head = ParagraphStyle("h", parent=bold, fontSize=9)
    head_right = ParagraphStyle("hr", parent=head, alignment=TA_RIGHT)
    company_name = ParagraphStyle("cn", parent=bold, fontSize=15, leading=19)
    title = ParagraphStyle("t", parent=bold, fontSize=20, leading=24, alignment=TA_RIGHT)

    def p(text, style=normal):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    def lines_block(rows, style=normal):
        text = [escape(str(r)) for r in rows if r]
        return Paragraph("<br/>".join(text), style)

    footer_text = data.get("footer", "")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(18 * mm, 10 * mm, f"Quotation {number}" + (f"  |  {footer_text}" if footer_text else ""))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
        title=f"Quotation {number}", author=company.get("name", ""),
    )
    width = A4[0] - 36 * mm
    story = []

    # Header: company on the left, QUOTATION on the right
    company_lines = [company.get("address"), company.get("email"), company.get("phone")]
    header = Table(
        [[[p(company.get("name", "Company name"), company_name), lines_block(company_lines, small)],
          p("QUOTATION", title)]],
        colWidths=[width * 0.62, width * 0.38],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [header, Spacer(1, 4 * mm), HRFlowable(width="100%", thickness=1, color=colors.black),
              Spacer(1, 4 * mm)]

    # Customer and quotation details
    cust_lines = [customer.get("name"), customer.get("company"), customer.get("address"), customer.get("email")]
    meta = Table(
        [[p("Quotation no.", small), p(number, bold)],
         [p("Date", small), p(quote_date)],
         [p("Valid until", small), p(valid_until)]],
        colWidths=[26 * mm, 40 * mm],
    )
    meta.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    details = Table(
        [[[p("Prepared for", small), lines_block(cust_lines, normal)], meta]],
        colWidths=[width * 0.58, width * 0.42],
    )
    details.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [details, Spacer(1, 6 * mm)]

    # Items table
    rows = [[p("#", head), p("Description", head), p("Qty", head_right), p(f"Unit price ({currency})", head_right),
             p("Disc.", head_right), p(f"Amount ({currency})", head_right)]]
    for n, ln in enumerate(totals["lines"], start=1):
        rows.append([p(n), p(ln["description"]), p(_qty(ln["quantity"]), right), p(_fmt(ln["unit_price"]), right),
                     p(_pct(ln["discount"]) if ln["discount"] else "-", right), p(_fmt(ln["amount"]), right)])
    items_table = Table(rows, colWidths=[9 * mm, width - 9 * mm - 14 * mm - 30 * mm - 16 * mm - 32 * mm,
                                         14 * mm, 30 * mm, 16 * mm, 32 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [items_table, Spacer(1, 4 * mm)]

    # Totals
    trows = [[p("Subtotal", right), p(_fmt(totals["subtotal"]), right)]]
    if totals["discount_rate"]:
        trows.append([p(f"Discount ({_pct(totals['discount_rate'])})", right), p("-" + _fmt(totals["discount_amount"]), right)])
        trows.append([p("Amount after discount", right), p(_fmt(totals["taxable_amount"]), right)])
    if totals["tax_rate"]:
        trows.append([p(f"Tax ({_pct(totals['tax_rate'])})", right), p(_fmt(totals["tax_amount"]), right)])
    trows.append([p(f"Total ({currency})", right_bold), p(_fmt(totals["total"]), right_bold)])
    totals_table = Table(trows, colWidths=[40 * mm, 32 * mm], hAlign="RIGHT")
    totals_table.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(totals_table)

    # Notes, terms and acceptance
    closing = []
    if data.get("notes"):
        closing += [Spacer(1, 8 * mm), p("Notes", bold), Spacer(1, 1 * mm), p(data["notes"], small)]
    if data.get("terms"):
        closing += [Spacer(1, 5 * mm), p("Terms and conditions", bold), Spacer(1, 1 * mm), p(data["terms"], small)]
    sign = Table(
        [[p("Prepared by", small), "", p("Customer acceptance (signature and date)", small)],
         ["", "", ""]],
        colWidths=[width * 0.42, width * 0.08, width * 0.42], hAlign="LEFT", rowHeights=[None, 12 * mm],
    )
    sign.setStyle(TableStyle([("LINEBELOW", (0, 1), (0, 1), 0.6, colors.black),
                              ("LINEBELOW", (2, 1), (2, 1), 0.6, colors.black),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    closing += [Spacer(1, 10 * mm), sign]
    story.append(KeepTogether(closing))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return totals


# ---------------------------------------------------------------------------
# 3. CHECKED EXAMPLES
# Every expected number below was worked out by hand first.
# ---------------------------------------------------------------------------

SAMPLE = {
    "quotation_number": "Q-2026-001",
    "date": "2026-11-26",
    "valid_days": 30,
    "currency": "USD",
    "company": {"name": "Example Company", "address": "12 Main Street, Rawalpindi",
                "email": "sales@example.com", "phone": "+92 300 0000000"},
    "customer": {"name": "John Smith", "company": "Smith Traders", "address": "45 Market Road, Lahore",
                 "email": "john@smithtraders.example"},
    "items": [
        {"description": "Business laptop 15 inch, 16 GB RAM, 512 GB SSD", "quantity": 25,
         "unit_price": 800, "discount": 0.05},
        {"description": "Wireless mouse", "quantity": 25, "unit_price": 10},
    ],
    "discount": 0.02,
    "tax_rate": 0.17,
    "notes": "Prices include delivery to the customer's office.",
    "terms": "Payment due within 14 days of acceptance. Prices valid until the date shown above.",
}


def _expect_error(data, text):
    try:
        calculate_quotation(data)
    except ValueError as err:
        assert text in str(err), (text, str(err))
        return
    raise AssertionError(f"expected an error containing {text!r}")


def _run_checks():
    # Laptops 25 x 800 x 0.95 = 19000.00, mice 25 x 10 = 250.00, subtotal 19250.00
    # Discount 2% = 385.00, taxable 18865.00, tax 17% = 3207.05, total 22072.05
    t = calculate_quotation(SAMPLE)
    assert [ln["amount"] for ln in t["lines"]] == [19000.00, 250.00]
    assert t["subtotal"] == 19250.00
    assert t["discount_amount"] == 385.00
    assert t["taxable_amount"] == 18865.00
    assert t["tax_amount"] == 3207.05
    assert t["total"] == 22072.05

    # No discount, no tax: total equals the sum of the lines
    plain = {"items": [{"description": "Service", "quantity": 2, "unit_price": 150.50}]}
    t = calculate_quotation(plain)
    assert t["total"] == 301.00 and t["tax_amount"] == 0 and t["discount_amount"] == 0

    # Rounding: 3 x 0.333 = 0.999 rounds half-up to 1.00
    t = calculate_quotation({"items": [{"description": "Part", "quantity": 3, "unit_price": 0.333}]})
    assert t["total"] == 1.00

    # Rounding: 1 x 0.125 = 0.125 rounds half-up to 0.13 (plain floats can give 0.12)
    t = calculate_quotation({"items": [{"description": "Part", "quantity": 1, "unit_price": 0.125}]})
    assert t["total"] == 0.13

    # Bad input must be rejected with a clear message
    _expect_error({"items": []}, "at least one item")
    _expect_error({"items": [{"description": "X", "quantity": 0, "unit_price": 5}]}, "greater than 0")
    _expect_error({"items": [{"description": "X", "quantity": 1, "unit_price": -5}]}, "cannot be negative")
    _expect_error({"items": [{"description": "", "quantity": 1, "unit_price": 5}]}, "description is required")
    _expect_error({**plain, "tax_rate": 17}, "looks like a percent number")
    _expect_error({**plain, "discount": 10}, "looks like a percent number")
    _expect_error({"items": [{"description": "X", "quantity": "abc", "unit_price": 5}]}, "must be a number")

    print("All checks passed.")


if __name__ == "__main__":
    _run_checks()
    if len(sys.argv) > 1 and sys.argv[1] == "sample":
        create_quotation_pdf(SAMPLE, "sample_quotation.pdf")
        print("Wrote sample_quotation.pdf")
