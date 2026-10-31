"""Delivery challan PDF for lifting entry (stock transfer not for sale)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
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
from .printing import amount_in_words
from .printing import money


class LiftingChallanPrinter:
    """Render lifting entry as delivery challan PDF."""

    def __init__(self, documents: DocumentService) -> None:
        self.documents = documents

    def create_pdf(
        self,
        document_id: str,
        destination: Path,
        copy_label: str = "original",
    ) -> Path:
        data = self.documents.get_document(document_id)
        if str(data["header"].get("document_type")) != "lifting_entry":
            raise ValidationError("Document is not a lifting entry")
        destination = destination.with_suffix(".pdf")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._build_pdf(destination, data, copy_label)
        return destination

    @staticmethod
    def _build_pdf(path: Path, data: dict[str, Any], copy_label: str) -> None:
        header = data["header"]
        lines = data["lines"]
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "Title",
            parent=styles["Normal"],
            fontSize=11,
            alignment=TA_CENTER,
            spaceAfter=4,
        )
        bold_center = ParagraphStyle(
            "BoldCenter",
            parent=styles["Normal"],
            fontSize=13,
            alignment=TA_CENTER,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        )
        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
        )
        story: list[Any] = []
        meta = header.get("metadata") or {}
        dispatch = meta.get("dispatch_from") or header.get("from_place") or "KURUKHETRA"
        story.append(Paragraph("STOCK TRANSFER NOT FOR SALE", title))
        story.append(Paragraph(f"Subject to {dispatch} Jurisdiction", title))
        story.append(Spacer(1, 4))
        story.append(Paragraph(str(header.get("company_name") or "Company"), bold_center))
        story.append(
            Paragraph(str(header.get("company_address") or ""), title),
        )
        story.append(Spacer(1, 6))
        story.append(Paragraph("<u>DELIVERY CHALLAN</u>", bold_center))
        story.append(
            Paragraph(
                f"<b>{header.get('party_name') or ''}</b>",
                bold_center,
            ),
        )
        story.append(Spacer(1, 8))
        info = Table(
            [
                [
                    f"CHALLAN NO : {header.get('document_number') or ''}",
                    "",
                    f"DATED : {header.get('document_date') or ''}",
                ]
            ],
            colWidths=[70 * mm, 40 * mm, 60 * mm],
        )
        info.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ]
            )
        )
        story.append(info)
        story.append(Spacer(1, 6))
        table_data = [
            [
                "S.No",
                "PARTY NAME",
                "ITEM NAME",
                "Bill No.",
                "Date of Purchase",
                "Packing",
                "Bags",
                "Weight",
                "Rate",
                "Amount",
            ]
        ]
        total_bags = Decimal("0")
        total_weight = Decimal("0")
        total_amount_paise = 0
        for index, line in enumerate(lines, start=1):
            line_meta = line.get("metadata") or {}
            reference = str(line_meta.get("reference") or line.get("source_reference_number") or "")
            bill_no = reference.split("-")[0] if reference else ""
            bill_date = ""
            if "/" in reference:
                parts = reference.split("-")
                if len(parts) >= 2:
                    bill_date = parts[-1]
            qty = Decimal(str(line_meta.get("qty") or line.get("bags_scaled") or 0))
            weight = Decimal(str(line_meta.get("weight") or 0))
            if weight <= 0:
                scale = int(line.get("quantity_scale") or 3)
                weight = Decimal(str(line.get("quantity_scaled") or 0)) / (Decimal(10) ** scale)
            rate_paise = int(line.get("rate_paise") or 0)
            amount_paise = int(line.get("amount_paise") or 0)
            total_bags += qty
            total_weight += weight
            total_amount_paise += amount_paise
            packing = ""
            item_name = str(line_meta.get("item_name") or line.get("commodity_name") or "")
            if "35" in item_name.upper():
                packing = "35.00"
            table_data.append(
                [
                    str(index),
                    str(line_meta.get("party_name") or ""),
                    item_name,
                    bill_no,
                    bill_date,
                    packing,
                    f"{qty:.2f}",
                    f"{weight:.2f}",
                    f"{rate_paise / 100:.2f}",
                    f"{amount_paise / 100:.2f}",
                ]
            )
        table_data.append(
            [
                "",
                "",
                "",
                "",
                "",
                "Total",
                f"{total_bags:.2f}",
                f"{total_weight:.2f}",
                "",
                f"{total_amount_paise / 100:.2f}",
            ]
        )
        grid = Table(table_data, repeatRows=1, colWidths=[8 * mm, 28 * mm, 32 * mm, 14 * mm, 18 * mm, 14 * mm, 14 * mm, 16 * mm, 14 * mm, 18 * mm])
        grid.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ("ALIGN", (6, 1), (-1, -1), "RIGHT"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(grid)
        story.append(Spacer(1, 8))
        words = amount_in_words(total_amount_paise)
        footer = Table(
            [
                [
                    f"Rs. ({words.replace('Rupees ', '').replace(' Only', ' Only')})",
                    f"{total_amount_paise / 100:.2f}",
                ]
            ],
            colWidths=[140 * mm, 30 * mm],
        )
        footer.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#b8e6b8")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#b8e6b8")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ]
            )
        )
        story.append(footer)
        story.append(Spacer(1, 10))
        meta_block = Table(
            [
                [f"VEHICLE NO : {header.get('vehicle_number') or 'N/A'}"],
                [f"G.R. NO : {header.get('gr_number') or 'N/A'}"],
                [f"DRIVER NAME : {header.get('driver_name') or 'N/A'}"],
                [f"TRANSPORTER : {meta.get('transport') or ''}"],
                [f"POLICY DETAIL : {meta.get('policy_no') or ''}"],
                [f"USER NAME : {meta.get('user_name') or 'User'}"],
            ],
            colWidths=[170 * mm],
        )
        meta_block.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9)]))
        story.append(meta_block)
        story.append(Spacer(1, 16))
        story.append(
            Paragraph(
                f"For {header.get('company_name') or 'Company'}<br/><br/>AUTHORISED SIGNATORY",
                ParagraphStyle(
                    "Sign",
                    parent=styles["Normal"],
                    alignment=2,
                    fontSize=9,
                ),
            )
        )
        if copy_label.lower() != "original":
            story.insert(0, Paragraph(copy_label.upper(), title))
        doc.build(story)
