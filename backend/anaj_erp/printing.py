"""A4 invoice PDF generation and Windows print dispatch."""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

from .documents import DocumentService
from .errors import ValidationError

COPY_LABELS = {"original", "duplicate", "triplicate"}
ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _under_thousand(value: int) -> str:
    """Convert a value below 1000 to English words."""
    parts: list[str] = []
    if value >= 100:
        parts.extend([ONES[value // 100], "Hundred"])
        value %= 100
    if value >= 20:
        parts.append(TENS[value // 10])
        value %= 10
    if value:
        parts.append(ONES[value])
    return " ".join(parts)


def amount_in_words(paise: int) -> str:
    """Convert non-negative paise to Indian rupee wording."""
    if paise < 0:
        raise ValidationError("Amount in words cannot format a negative value")
    rupees, remaining_paise = divmod(paise, 100)
    if rupees == 0:
        words = "Zero"
    else:
        groups = [
            (10_000_000, "Crore"),
            (100_000, "Lakh"),
            (1_000, "Thousand"),
        ]
        parts: list[str] = []
        remaining = rupees
        for divisor, label in groups:
            count, remaining = divmod(remaining, divisor)
            if count:
                parts.extend([_under_thousand(count), label])
        if remaining:
            parts.append(_under_thousand(remaining))
        words = " ".join(parts)
    suffix = (
        f" and {_under_thousand(remaining_paise)} Paise"
        if remaining_paise
        else ""
    )
    return f"Rupees {words}{suffix} Only"


def money(paise: int) -> str:
    """Format integer paise for bill cells."""
    return f"{paise / 100:,.2f}"


class InvoicePrinter:
    """Render stored documents to deterministic A4 PDF bills."""

    def __init__(self, documents: DocumentService) -> None:
        """Use a document service as the only invoice data source."""
        self.documents = documents

    def create_pdf(
        self,
        document_id: str,
        destination: Path,
        copy_label: str = "original",
    ) -> Path:
        """Create an A4 bill and atomically move it to destination."""
        normalized_copy = copy_label.lower()
        if normalized_copy not in COPY_LABELS:
            raise ValidationError("Copy label must be original, duplicate or triplicate")
        data = self.documents.get_document(document_id)
        header = data["header"]
        lines = data["lines"]
        charges = data["charges"]
        destination = destination.with_suffix(".pdf")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            self._build_pdf(temporary_path, header, lines, charges, normalized_copy)
            temporary_path.replace(destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return destination

    @staticmethod
    def send_to_default_printer(path: Path) -> None:
        """Submit an existing PDF through the Windows shell print action."""
        if os.name != "nt":
            raise ValidationError("Direct printing is supported only on Windows")
        if not path.exists() or path.suffix.lower() != ".pdf":
            raise ValidationError("A valid PDF is required for printing")
        os.startfile(path, "print")

    @staticmethod
    def _build_pdf(
        path: Path,
        header: dict[str, Any],
        lines: list[dict[str, Any]],
        charges: list[dict[str, Any]],
        copy_label: str,
    ) -> None:
        """Build the ReportLab document."""
        styles = getSampleStyleSheet()
        centered = ParagraphStyle(
            "BillCenter",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            leading=12,
        )
        right = ParagraphStyle(
            "BillRight",
            parent=styles["Normal"],
            alignment=TA_RIGHT,
            leading=11,
        )
        title = ParagraphStyle(
            "BillTitle",
            parent=centered,
            fontSize=18,
            leading=21,
            spaceAfter=2,
        )
        document = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=11 * mm,
            rightMargin=11 * mm,
            topMargin=9 * mm,
            bottomMargin=9 * mm,
            title=f"{header['document_type']} {header['document_number']}",
        )
        story: list[Any] = [
            Paragraph(f"{copy_label.title()} Copy", right),
            Paragraph(str(header["company_name"] or "Company"), title),
            Paragraph(
                "<b>COMMISSION AGENTS &amp; GRAIN TRADERS</b><br/>"
                f"{header['company_address'] or ''}<br/>"
                f"GSTIN: {header['company_gstin'] or '-'} &nbsp;&nbsp; "
                f"PAN: {header['company_pan'] or '-'} &nbsp;&nbsp; "
                f"Phone: {header['phone'] or '-'}",
                centered,
            ),
            Spacer(1, 3 * mm),
        ]
        party_text = (
            f"<b>M/s:</b> {header['party_name'] or '-'}<br/>"
            f"{header['party_address'] or ''}<br/>"
            f"<b>GSTIN:</b> {header['party_gstin'] or '-'} &nbsp; "
            f"<b>PAN:</b> {header['party_pan'] or '-'}"
        )
        invoice_text = (
            f"<b>Invoice No.:</b> {header['document_number']}<br/>"
            f"<b>Date:</b> {header['document_date']}<br/>"
            f"<b>Due Date:</b> {header['due_date'] or '-'}<br/>"
            f"<b>From:</b> {header['from_place'] or '-'} &nbsp; "
            f"<b>To:</b> {header['to_place'] or '-'}"
        )
        details = Table(
            [[Paragraph(party_text, styles["Normal"]), Paragraph(invoice_text, styles["Normal"])]],
            colWidths=[118 * mm, 65 * mm],
        )
        details.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend(
            [
                details,
                Paragraph(
                    f"<b>Vehicle:</b> {header['vehicle_number'] or '-'} &nbsp;&nbsp; "
                    f"<b>Driver:</b> {header['driver_name'] or '-'} &nbsp;&nbsp; "
                    f"<b>GR No.:</b> {header['gr_number'] or '-'} &nbsp;&nbsp; "
                    f"<b>e-Way Bill:</b> {header['eway_bill_number'] or '-'}",
                    styles["Normal"],
                ),
                Spacer(1, 2 * mm),
            ]
        )
        line_data: list[list[str]] = [
            ["Description", "HSN", "Bags", "Quantity", "Rate", "Amount (Rs.)"]
        ]
        total_bags = Decimal("0")
        total_quantity = Decimal("0")
        for line in lines:
            bags = Decimal(int(line["bags_scaled"])) / (
                Decimal(10) ** int(line["bag_scale"])
            )
            quantity = Decimal(int(line["quantity_scaled"])) / (
                Decimal(10) ** int(line["quantity_scale"])
            )
            total_bags += bags
            total_quantity += quantity
            line_data.append(
                [
                    str(line["description"]),
                    str(line["hsn_code"] or ""),
                    str(bags),
                    str(quantity),
                    money(int(line["rate_paise"])),
                    money(int(line["amount_paise"])),
                ]
            )
        line_table = Table(
            line_data,
            colWidths=[57 * mm, 20 * mm, 18 * mm, 27 * mm, 28 * mm, 33 * mm],
            repeatRows=1,
        )
        line_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend([line_table, Spacer(1, 2 * mm)])
        charge_data: list[list[str]] = [["Expenses / Taxes", "Rate", "Amount (Rs.)"]]
        for charge in charges:
            charge_data.append(
                [
                    str(charge["label"]),
                    str(charge["rate_decimal"]),
                    money(int(charge["final_amount_paise"])),
                ]
            )
        charge_data.extend(
            [
                ["VALUE", "", money(int(header["subtotal_paise"]))],
                ["TOTAL EXPENSES", "", money(int(header["total_charges_paise"]))],
                ["TOTAL TAX", "", money(int(header["total_tax_paise"]))],
                ["GRAND TOTAL", "", money(int(header["grand_total_paise"]))],
            ]
        )
        charges_table = Table(
            charge_data,
            colWidths=[110 * mm, 28 * mm, 45 * mm],
            hAlign="RIGHT",
        )
        charges_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ]
            )
        )
        story.extend(
            [
                Paragraph(
                    f"<b>Total Quantity:</b> {total_quantity} &nbsp;&nbsp; "
                    f"<b>Total Bag Units:</b> {total_bags}",
                    styles["Normal"],
                ),
                charges_table,
                Spacer(1, 2 * mm),
                Paragraph(
                    f"<b>{amount_in_words(int(header['grand_total_paise']))}</b>",
                    styles["Normal"],
                ),
                Spacer(1, 3 * mm),
                Paragraph(
                    "* Interest may be charged according to configured payment terms.<br/>"
                    "E. &amp; O. E.",
                    styles["Normal"],
                ),
                Spacer(1, 12 * mm),
                Paragraph(f"For {header['company_name']}<br/><br/>Authorized Signature", right),
            ]
        )
        document.build(story)
