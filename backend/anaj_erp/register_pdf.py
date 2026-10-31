"""PDF output for cash book, day book, and posted vouchers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

from .errors import ValidationError
from .printing import InvoicePrinter


def _money(paise: int) -> str:
    return f"{paise / 100:,.2f}"


class RegisterPdfPrinter:
    """Generate A4 register PDFs from report datasets."""

    @staticmethod
    def cash_book(
        company_name: str,
        cash_book: dict[str, Any],
        *,
        date_from: str,
        date_to: str,
        destination: Path,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(destination), pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"<b>{company_name}</b>", styles["Title"]),
            Paragraph(
                f"<b>Cash Book</b> — {date_from} to {date_to}",
                styles["Heading2"],
            ),
            Spacer(1, 4 * mm),
        ]
        rows: list[list[str]] = [["Date", "Particulars", "Receipt", "Payment", "Balance"]]
        for entry in cash_book.get("entries", []):
            debit = int(entry.get("debit_paise", 0))
            credit = int(entry.get("credit_paise", 0))
            rows.append(
                [
                    str(entry.get("entry_date", "")),
                    str(entry.get("narration") or entry.get("account_name", "")),
                    _money(debit) if debit else "",
                    _money(credit) if credit else "",
                    _money(int(entry.get("running_balance_paise", 0))),
                ]
            )
        closing = int(cash_book.get("closing_balance_paise", 0))
        rows.append(["", "Closing balance", "", "", _money(closing)])
        table = Table(rows, colWidths=[22 * mm, 78 * mm, 28 * mm, 28 * mm, 28 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return destination

    @staticmethod
    def day_book(
        company_name: str,
        rows: list[dict[str, Any]],
        *,
        date_from: str,
        date_to: str,
        destination: Path,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(destination), pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"<b>{company_name}</b>", styles["Title"]),
            Paragraph(f"<b>Day Book</b> — {date_from} to {date_to}", styles["Heading2"]),
            Spacer(1, 4 * mm),
        ]
        data: list[list[str]] = [["Date", "Voucher", "Account", "Debit", "Credit"]]
        for row in rows:
            data.append(
                [
                    str(row.get("entry_date", "")),
                    str(row.get("voucher_number", "")),
                    str(row.get("account_name", "")),
                    _money(int(row.get("debit_paise", 0))) if int(row.get("debit_paise", 0)) else "",
                    _money(int(row.get("credit_paise", 0))) if int(row.get("credit_paise", 0)) else "",
                ]
            )
        table = Table(data, colWidths=[22 * mm, 28 * mm, 62 * mm, 32 * mm, 32 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return destination

    @staticmethod
    def voucher(
        company_name: str,
        voucher: dict[str, Any],
        lines: list[dict[str, Any]],
        destination: Path,
    ) -> Path:
        if not lines:
            raise ValidationError("Voucher has no lines to print")
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(destination), pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"<b>{company_name}</b>", styles["Title"]),
            Paragraph(
                f"<b>{str(voucher.get('voucher_type', 'Voucher')).replace('_', ' ').title()}</b> "
                f"No. {voucher.get('voucher_number', '')} — {voucher.get('voucher_date', '')}",
                styles["Heading2"],
            ),
            Spacer(1, 4 * mm),
        ]
        data: list[list[str]] = [["Account", "Debit", "Credit", "Narration"]]
        for line in lines:
            data.append(
                [
                    str(line.get("account_name", "")),
                    _money(int(line.get("debit_paise", 0))) if int(line.get("debit_paise", 0)) else "",
                    _money(int(line.get("credit_paise", 0))) if int(line.get("credit_paise", 0)) else "",
                    str(line.get("narration", "")),
                ]
            )
        table = Table(data, colWidths=[70 * mm, 30 * mm, 30 * mm, 55 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (2, -1), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return destination

    @classmethod
    def print_path(cls, path: Path) -> None:
        InvoicePrinter.send_to_default_printer(path)
