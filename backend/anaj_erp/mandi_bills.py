"""APMC-style J-Form, I-Form, and ledger print layouts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .documents import DocumentService
from .errors import ValidationError
from .escpos import COPY_LABELS, EscPosBuilder
from .mandi_statutory_html import MandiStatutoryHtmlRenderer
from .print_designer import merge_print_design, render_template_lines
from .printing import InvoicePrinter, amount_in_words, money


class MandiBillPrinter:
    """J-Form / I-Form / ledger layouts for screen and dot-matrix."""

    def __init__(self, documents: DocumentService) -> None:
        self.documents = documents

    def create_mandi_pdf(
        self,
        document_id: str,
        destination: Path,
        *,
        copy_label: str = "original",
        design: dict[str, Any] | None = None,
        visible_columns: dict[str, bool] | None = None,
    ) -> Path:
        data = self.documents.get_document(document_id)
        header = data["header"]
        doc_type = str(header.get("document_type", ""))
        if doc_type in {"form_j", "form_i_credit"}:
            return self._j_form_pdf(
                destination,
                header,
                data["lines"],
                data["charges"],
                copy_label,
                design,
                visible_columns,
            )
        if doc_type in {"form_i_debit", "sale_invoice"}:
            return self._i_form_pdf(
                destination,
                header,
                data["lines"],
                data["charges"],
                copy_label,
                design,
                visible_columns,
            )
        return InvoicePrinter(self.documents).create_pdf(
            document_id,
            destination,
            copy_label=copy_label,
        )

    def create_statutory_html(
        self,
        document_id: str,
        destination: Path,
        *,
        columns: int = 80,
        copy_count: int = 3,
        design: dict[str, Any] | None = None,
    ) -> Path:
        data = self.documents.get_document(document_id)
        renderer = MandiStatutoryHtmlRenderer()
        return renderer.write_html_file(
            destination,
            data["header"],
            data["lines"],
            data["charges"],
            columns=columns,
            copy_count=copy_count,
            design=design,
        )

    def create_escpos_copies(
        self,
        document_id: str,
        *,
        columns: int = 80,
        copy_count: int = 3,
        design: dict[str, Any] | None = None,
        visible_columns: dict[str, bool] | None = None,
    ) -> bytes:
        data = self.documents.get_document(document_id)
        header = data["header"]
        merged = merge_print_design(design)
        copies = min(max(copy_count, 1), 3)
        builder = EscPosBuilder(columns=columns)
        vis = visible_columns or {}
        show_moisture = vis.get("moisture", True)
        show_tare = vis.get("tare", True)
        doc_type = str(header.get("document_type") or "")
        is_j_form = doc_type in {"form_j", "form_i_credit"}
        for index in range(copies):
            label = COPY_LABELS[index][1] if index < len(COPY_LABELS) else f"COPY {index + 1}"
            builder.double_height(True)
            builder.bold(True)
            builder.text(label)
            builder.double_height(False)
            builder.bold(False)
            context = {
                "company_name": str(header.get("company_name") or "Company"),
                "mandi_license_no": str(merged.get("mandi_license_no") or "-"),
                "city": str(header.get("from_place") or header.get("to_place") or "Local"),
                "custom_terms": str(merged.get("custom_terms") or ""),
            }
            for line in render_template_lines(list(merged.get("header_lines", [])), context):
                builder.text(line)
            builder.rule("=")
            if is_j_form:
                builder.text("FARMER SALE PATTI / J-FORM")
                builder.text(
                    f"J-No {header.get('document_number')}  Dt {header.get('document_date')}"
                )
                builder.text(f"Farmer: {header.get('party_name') or '-'}")
                builder.text(f"Lic: {merged.get('mandi_license_no') or '-'}")
                builder.rule("-")
                builder.text(
                    f"{'Crop':<14}{'Bags':>5}{'WtQtl':>8}{'Rate':>9}{'Amount':>10}"
                )
                builder.rule("-")
            else:
                builder.text(
                    f"Bill {header.get('document_number')}  Date {header.get('document_date')}"
                )
                builder.text(f"Party: {header.get('party_name') or '-'}")
            for line in data["lines"]:
                bags = line.get("bags_scaled", 0)
                qty = int(line.get("quantity_scaled", 0)) / 1000
                desc = str(
                    line.get("commodity_name") or line.get("description") or "Item"
                )[:14]
                rate = money(int(line.get("rate_paise", 0)))
                amt = money(int(line.get("amount_paise", 0)))
                if is_j_form:
                    builder.text(
                        f"{desc:<14}{str(bags):>5}{qty:>8.3f}{rate:>9}{amt:>10}"
                    )
                else:
                    builder.text(
                        f"{line.get('description', 'Item')[:28]}  "
                        f"B:{bags} Q:{qty:.3f} Amt:{amt}"
                    )
                if show_moisture:
                    builder.text("  Moisture: (as posted)")
                if show_tare:
                    builder.text("  Tare: (as posted)")
            builder.rule("-")
            if is_j_form:
                builder.text(f"{'Deduction':<24}{'Amount':>10}")
                builder.rule("-")
            for charge in data["charges"]:
                builder.text(
                    f"{str(charge.get('label', ''))[:24]:24} "
                    f"{money(int(charge.get('final_amount_paise', 0))):>10}"
                )
            builder.bold(True)
            builder.text(f"NET PAYABLE {money(int(header.get('grand_total_paise', 0)))}")
            builder.bold(False)
            builder.text(amount_in_words(int(header.get("grand_total_paise", 0))))
            for line in render_template_lines(list(merged.get("footer_lines", [])), context):
                builder.text(line)
            if merged.get("show_bank_qr") and merged.get("bank_qr_payload"):
                builder.text(f"QR/UPI: {merged['bank_qr_payload']}")
            builder.feed(2)
            builder.cut()
        return builder.to_bytes()

    def ledger_statement_pdf(
        self,
        *,
        party_name: str,
        rows: list[dict[str, Any]],
        destination: Path,
        title: str,
        design: dict[str, Any] | None = None,
    ) -> Path:
        """Muddat Bilti / Nakal Khata style customer ledger."""
        merged = merge_print_design(design)
        destination = destination.with_suffix(".pdf")
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(destination), pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(title, styles["Heading1"]),
            Paragraph(str(party_name), styles["Heading3"]),
        ]
        context = {
            "company_name": "",
            "mandi_license_no": str(merged.get("mandi_license_no") or ""),
            "city": "",
            "custom_terms": str(merged.get("custom_terms") or ""),
        }
        for line in render_template_lines(list(merged.get("header_lines", [])), context):
            story.append(Paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 6))
        table_data = [["Date", "Particulars", "Debit", "Credit", "Balance"]]
        for row in rows:
            table_data.append(
                [
                    str(row.get("date", "")),
                    str(row.get("particulars", "")),
                    str(row.get("debit", "")),
                    str(row.get("credit", "")),
                    str(row.get("balance", "")),
                ]
            )
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return destination

    def _j_form_pdf(
        self,
        destination: Path,
        header: dict[str, Any],
        lines: list[dict[str, Any]],
        charges: list[dict[str, Any]],
        copy_label: str,
        design: dict[str, Any] | None,
        visible_columns: dict[str, bool] | None,
    ) -> Path:
        merged = merge_print_design(design)
        destination = destination.with_suffix(".pdf")
        doc = SimpleDocTemplate(str(destination), pagesize=A4)
        styles = getSampleStyleSheet()
        centered = ParagraphStyle("c", parent=styles["Normal"], alignment=1)
        story = [
            Paragraph(f"{copy_label.title()} Copy — J-FORM (Farmer Sale Patti)", centered),
            Paragraph("<b>FARMER SALE PATTI / J-FORM</b>", styles["Heading2"]),
        ]
        context = {
            "company_name": str(header.get("company_name") or ""),
            "mandi_license_no": str(merged.get("mandi_license_no") or "-"),
            "city": str(header.get("from_place") or ""),
            "custom_terms": str(merged.get("custom_terms") or ""),
        }
        for line in render_template_lines(list(merged.get("header_lines", [])), context):
            story.append(Paragraph(line, centered))
        story.append(
            Paragraph(
                f"Farmer: <b>{header.get('party_name') or '-'}</b> &nbsp; "
                f"Patti No: <b>{header.get('document_number')}</b> &nbsp; "
                f"Date: {header.get('document_date')}",
                styles["Normal"],
            )
        )
        gross = int(header.get("subtotal_paise", 0))
        deduct_codes = {"TULA", "PALLEDARI", "SEWING", "GRADING", "MARKET_FEE", "HRDF"}
        deductions = [
            charge for charge in charges if str(charge.get("code", "")) in deduct_codes
        ]
        advance = int(header.get("advance_cash_paise", 0))
        net = int(header.get("grand_total_paise", 0))
        vis = visible_columns or {}
        detail = [
            ["Particular", "Amount (Rs.)"],
            ["Gross value", money(gross)],
        ]
        for charge in deductions:
            detail.append([str(charge.get("label")), money(int(charge.get("final_amount_paise", 0)))])
        if vis.get("moisture", True):
            detail.append(["Moisture adjustment", "—"])
        if vis.get("tare", True):
            detail.append(["Tare / bardana", "—"])
        detail.extend(
            [
                ["Cash advances", money(advance)],
                ["NET PAYABLE TO FARMER", money(net)],
            ]
        )
        table = Table(detail, colWidths=[120 * mm, 50 * mm])
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
        story.extend([Spacer(1, 4), table, Paragraph(amount_in_words(net), styles["Italic"])])
        doc.build(story)
        return destination

    def _i_form_pdf(
        self,
        destination: Path,
        header: dict[str, Any],
        lines: list[dict[str, Any]],
        charges: list[dict[str, Any]],
        copy_label: str,
        design: dict[str, Any] | None,
        visible_columns: dict[str, bool] | None,
    ) -> Path:
        merged = merge_print_design(design)
        destination = destination.with_suffix(".pdf")
        doc = SimpleDocTemplate(str(destination), pagesize=A4)
        styles = getSampleStyleSheet()
        centered = ParagraphStyle("c", parent=styles["Normal"], alignment=1)
        story = [
            Paragraph(f"{copy_label.title()} Copy — I-FORM / Vikraya Parchi", centered),
            Paragraph("<b>VIKRAYA PARCHI (Buyer Invoice)</b>", styles["Heading2"]),
        ]
        context = {
            "company_name": str(header.get("company_name") or ""),
            "mandi_license_no": str(merged.get("mandi_license_no") or "-"),
            "city": str(header.get("to_place") or ""),
            "custom_terms": str(merged.get("custom_terms") or ""),
        }
        for line in render_template_lines(list(merged.get("header_lines", [])), context):
            story.append(Paragraph(line, centered))
        story.append(
            Paragraph(
                f"Buyer: <b>{header.get('party_name') or '-'}</b> &nbsp; "
                f"Invoice: <b>{header.get('document_number')}</b>",
                styles["Normal"],
            )
        )
        line_rows = [["Item", "Qty", "Rate", "Amount"]]
        for line in lines:
            qty = int(line.get("quantity_scaled", 0)) / 1000
            line_rows.append(
                [
                    str(line.get("description", "")),
                    f"{qty:.3f}",
                    money(int(line.get("rate_paise", 0))),
                    money(int(line.get("amount_paise", 0))),
                ]
            )
        line_table = Table(line_rows, repeatRows=1)
        line_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
        story.append(line_table)
        cess_rows = [["Statutory / loading charges", "Amount (Rs.)"]]
        for charge in charges:
            cess_rows.append(
                [
                    str(charge.get("label")),
                    money(int(charge.get("final_amount_paise", 0))),
                ]
            )
        cess_rows.append(["GRAND TOTAL", money(int(header.get("grand_total_paise", 0)))])
        story.append(Spacer(1, 6))
        story.append(Table(cess_rows, colWidths=[120 * mm, 50 * mm]))
        doc.build(story)
        return destination
