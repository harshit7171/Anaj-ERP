"""Competitive mandi features: messaging links, advanced reports, bank recon, attachments."""

from __future__ import annotations

import csv
import json
import re
import shutil
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .database import DatabaseManager
from .database import utc_now
from .errors import ValidationError
from .mandi_business import statutory_turnover_alerts
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

TCS_SECTION_206C_1H_THRESHOLD_PAISE = 50_00_000 * 100  # ₹50 lakh


def whatsapp_url(phone: str, message: str) -> str:
    """Build a WhatsApp deep link (opens app/Web with prefilled text)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        digits = f"91{digits}"
    if not digits:
        return f"https://wa.me/?text={quote(message)}"
    return f"https://wa.me/{digits}?text={quote(message)}"


class ModernFeaturesService:
    """Desktop-first implementations; full WhatsApp Business API is operator-configured later."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.attachments_dir = databases.data_dir / "attachments" / company_id

    def executive_metrics(self, financial_year_id: str, *, as_of_date: str) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            arrivals = connection.execute(
                """
                SELECT
                    COALESCE(SUM(dl.bags_scaled), 0) AS bags,
                    COALESCE(SUM(dl.quantity_scaled), 0) AS quantity_scaled
                FROM document d
                JOIN document_line dl ON dl.document_id = d.document_id
                WHERE d.financial_year_id = ? AND d.status = 'posted'
                    AND d.document_date = ?
                    AND d.document_type IN (
                        'inward', 'gate_pass', 'form_j', 'kachi_purchase',
                        'mandi_purchase', 'lifting_entry'
                    )
                """,
                (financial_year_id, as_of_date),
            ).fetchone()
            cash_row = connection.execute(
                """
                SELECT a.account_id, a.name,
                    COALESCE(SUM(vl.debit_paise), 0) - COALESCE(SUM(vl.credit_paise), 0)
                    + a.opening_debit_paise - a.opening_credit_paise AS balance_paise
                FROM account a
                LEFT JOIN voucher_line vl ON vl.account_id = a.account_id
                LEFT JOIN voucher v ON v.voucher_id = vl.voucher_id
                    AND v.financial_year_id = ? AND v.status = 'posted'
                WHERE a.is_deleted = 0 AND a.account_type = 'asset'
                    AND a.name LIKE '%cash%' COLLATE NOCASE
                GROUP BY a.account_id, a.name
                ORDER BY balance_paise DESC LIMIT 1
                """,
                (financial_year_id,),
            ).fetchone()
            bank_rows = connection.execute(
                """
                SELECT a.name,
                    COALESCE(SUM(vl.debit_paise), 0) - COALESCE(SUM(vl.credit_paise), 0)
                    + a.opening_debit_paise - a.opening_credit_paise AS balance_paise
                FROM account a
                LEFT JOIN voucher_line vl ON vl.account_id = a.account_id
                LEFT JOIN voucher v ON v.voucher_id = vl.voucher_id
                    AND v.financial_year_id = ? AND v.status = 'posted'
                WHERE a.is_deleted = 0 AND a.account_type = 'asset'
                    AND (a.name LIKE '%bank%' OR a.name LIKE '%account%' COLLATE NOCASE)
                    AND a.name NOT LIKE '%cash%' COLLATE NOCASE
                GROUP BY a.account_id, a.name
                ORDER BY a.name
                LIMIT 5
                """,
                (financial_year_id,),
            ).fetchall()
            dues = connection.execute(
                """
                SELECT p.name, d.balance_paise, d.due_date, d.document_number
                FROM document d
                JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ? AND d.status = 'posted'
                    AND d.balance_paise > 0
                ORDER BY d.balance_paise DESC
                LIMIT 5
                """,
                (financial_year_id,),
            ).fetchall()
            sales_today = connection.execute(
                """
                SELECT COALESCE(SUM(grand_total_paise), 0) AS total,
                    COUNT(*) AS bill_count
                FROM document
                WHERE financial_year_id = ? AND status = 'posted'
                    AND document_date = ?
                    AND document_type IN ('sale_invoice', 'form_i_debit')
                """,
                (financial_year_id, as_of_date),
            ).fetchone()
            payables = connection.execute(
                """
                SELECT COALESCE(SUM(
                    vl.credit_paise - vl.debit_paise
                ), 0) AS payable_paise
                FROM voucher_line vl
                JOIN voucher v ON v.voucher_id = vl.voucher_id
                JOIN account a ON a.account_id = vl.account_id
                WHERE v.financial_year_id = ? AND v.status = 'posted'
                    AND a.account_type = 'liability'
                """,
                (financial_year_id,),
            ).fetchone()
            receivables = connection.execute(
                """
                SELECT COALESCE(SUM(balance_paise), 0) AS receivable_paise
                FROM document
                WHERE financial_year_id = ? AND status = 'posted'
                    AND balance_paise > 0
                """,
                (financial_year_id,),
            ).fetchone()
        return {
            "today_arrivals_bags": int(arrivals["bags"]) if arrivals else 0,
            "today_arrivals_quantity_scaled": int(arrivals["quantity_scaled"]) if arrivals else 0,
            "cash_in_hand_paise": int(cash_row["balance_paise"]) if cash_row else 0,
            "cash_account_name": str(cash_row["name"]) if cash_row else "",
            "bank_balances": [
                {"name": str(r["name"]), "balance_paise": int(r["balance_paise"])}
                for r in bank_rows
            ],
            "top_outstanding_dues": [dict(r) for r in dues],
            "today_sales_paise": int(sales_today["total"]) if sales_today else 0,
            "today_sales_count": int(sales_today["bill_count"]) if sales_today else 0,
            "receivables_paise": int(receivables["receivable_paise"]) if receivables else 0,
            "payables_paise": int(payables["payable_paise"]) if payables else 0,
        }

    def threshold_alerts(self, financial_year_id: str) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            return statutory_turnover_alerts(connection, financial_year_id)

    def whatsapp_for_document(self, document_id: str) -> dict[str, str]:
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT d.document_number, d.document_type, d.document_date,
                    d.grand_total_paise, d.balance_paise, p.name, p.phone
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.document_id = ?
                """,
                (document_id,),
            ).fetchone()
        if row is None:
            raise ValidationError("Document not found")
        label = str(row["document_type"]).replace("_", " ").title()
        message = (
            f"{label} No. {row['document_number']} dated {row['document_date']}\n"
            f"Amount: ₹{int(row['grand_total_paise']) / 100:,.2f}\n"
            f"Balance: ₹{int(row['balance_paise']) / 100:,.2f}\n"
            f"— Sent from Anaj ERP"
        )
        return {
            "message": message,
            "url": whatsapp_url(str(row["phone"] or ""), message),
            "party_name": str(row["name"] or ""),
        }

    def whatsapp_payment_reminder(self, party_id: str) -> dict[str, str]:
        with self.databases.connect(self.database_path) as connection:
            party = connection.execute(
                "SELECT name, phone FROM party WHERE party_id = ?", (party_id,)
            ).fetchone()
            if party is None:
                raise ValidationError("Party not found")
            total = connection.execute(
                """
                SELECT COALESCE(SUM(balance_paise), 0) AS due
                FROM document
                WHERE party_id = ? AND status = 'posted' AND balance_paise > 0
                """,
                (party_id,),
            ).fetchone()
        due = int(total["due"]) if total else 0
        message = (
            f"Dear {party['name']},\n"
            f"Kindly clear your outstanding balance of ₹{due / 100:,.2f} at the earliest.\n"
            f"— Accounts Department"
        )
        return {
            "message": message,
            "url": whatsapp_url(str(party["phone"] or ""), message),
        }

    def broker_commission_report(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    broker.party_id AS broker_id,
                    broker.name AS broker_name,
                    COUNT(DISTINCT d.document_id) AS bill_count,
                    SUM(dl.amount_paise) AS business_paise
                FROM document d
                JOIN document_line dl ON dl.document_id = d.document_id
                JOIN party broker ON broker.party_id = dl.purchaser_party_id
                WHERE d.financial_year_id = ? AND d.status = 'posted'
                    AND d.document_date BETWEEN ? AND ?
                    AND broker.party_type = 'commission_agent'
                GROUP BY broker.party_id, broker.name
                ORDER BY business_paise DESC
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
            rate_row = connection.execute(
                """
                SELECT rate_decimal FROM charge_rule
                WHERE code = 'COMMISSION' AND is_deleted = 0
                ORDER BY effective_from DESC LIMIT 1
                """
            ).fetchone()
        rate = Decimal(str(rate_row["rate_decimal"])) if rate_row else Decimal("1")
        report: list[dict[str, Any]] = []
        for row in rows:
            business = int(row["business_paise"])
            commission = int((Decimal(business) * rate / Decimal(100)).quantize(Decimal("1")))
            report.append(
                {
                    "broker_id": str(row["broker_id"]),
                    "broker_name": str(row["broker_name"]),
                    "bill_count": int(row["bill_count"]),
                    "business_paise": business,
                    "commission_rate_percent": str(rate),
                    "commission_paise": commission,
                    "net_payable_paise": commission,
                }
            )
        return report

    def item_wise_profitability(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    c.commodity_id,
                    c.name AS item_name,
                    SUM(CASE WHEN d.document_type IN ('sale_invoice', 'form_i_debit')
                        THEN dl.amount_paise ELSE 0 END) AS sale_paise,
                    SUM(CASE WHEN d.document_type IN (
                        'purchase_invoice', 'kachi_purchase', 'mandi_purchase', 'gst_purchase'
                    ) THEN dl.amount_paise ELSE 0 END) AS purchase_paise
                FROM commodity c
                LEFT JOIN document_line dl ON dl.commodity_id = c.commodity_id
                LEFT JOIN document d ON d.document_id = dl.document_id
                    AND d.financial_year_id = ? AND d.status = 'posted'
                    AND d.document_date BETWEEN ? AND ?
                WHERE c.is_deleted = 0
                GROUP BY c.commodity_id, c.name
                HAVING sale_paise > 0 OR purchase_paise > 0
                ORDER BY c.name
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            sale = int(row["sale_paise"] or 0)
            purchase = int(row["purchase_paise"] or 0)
            charges = int(round(sale * 0.02)) if sale else 0
            profit = sale - purchase - charges
            result.append(
                {
                    "item_name": str(row["item_name"]),
                    "sale_paise": sale,
                    "purchase_paise": purchase,
                    "expense_paise": charges,
                    "profit_paise": profit,
                    "margin_percent": round(profit * 100 / sale, 2) if sale else 0,
                }
            )
        return result

    def blended_average_cost(
        self,
        financial_year_id: str,
        commodity_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT dl.quantity_scaled, dl.rate_paise, d.document_date, d.document_number
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                WHERE d.financial_year_id = ? AND d.status = 'posted'
                    AND dl.commodity_id = ?
                    AND d.document_date BETWEEN ? AND ?
                    AND d.document_type IN (
                        'purchase_invoice', 'kachi_purchase', 'mandi_purchase', 'gst_purchase'
                    )
                    AND dl.quantity_scaled > 0
                ORDER BY d.document_date
                """,
                (financial_year_id, commodity_id, date_from, date_to),
            ).fetchall()
        total_qty = 0
        total_value = 0
        lots: list[dict[str, Any]] = []
        for row in rows:
            qty = int(row["quantity_scaled"])
            rate = int(row["rate_paise"])
            total_qty += qty
            total_value += qty * rate
            lots.append(
                {
                    "document_number": str(row["document_number"]),
                    "document_date": str(row["document_date"]),
                    "quantity_scaled": qty,
                    "rate_paise": rate,
                }
            )
        avg_rate = int(total_value / total_qty) if total_qty else 0
        return {
            "commodity_id": commodity_id,
            "total_quantity_scaled": total_qty,
            "blended_rate_paise": avg_rate,
            "lots": lots,
        }

    def clause_44_export(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    p.name AS party_name,
                    p.gstin,
                    SUM(d.grand_total_paise) AS amount_paise,
                    CASE
                        WHEN p.gstin IS NOT NULL AND length(trim(p.gstin)) = 15
                        THEN 'registered'
                        ELSE 'unregistered'
                    END AS supplier_class
                FROM document d
                JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ? AND d.status = 'posted'
                    AND d.document_date BETWEEN ? AND ?
                    AND d.document_type IN (
                        'purchase_invoice', 'gst_purchase', 'mandi_purchase', 'kachi_purchase'
                    )
                GROUP BY p.party_id, p.name, p.gstin, supplier_class
                ORDER BY supplier_class, p.name
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        registered: list[dict[str, Any]] = []
        unregistered: list[dict[str, Any]] = []
        for row in rows:
            item = {
                "party_name": str(row["party_name"]),
                "gstin": str(row["gstin"] or ""),
                "amount_paise": int(row["amount_paise"]),
            }
            if str(row["supplier_class"]) == "registered":
                registered.append(item)
            else:
                unregistered.append(item)
        payload = {
            "report": "Income Tax Audit — Clause 44 (expenditure summary)",
            "period_from": date_from,
            "period_to": date_to,
            "registered_suppliers": registered,
            "unregistered_suppliers": unregistered,
        }
        return {"export": payload, "json": json.dumps(payload, indent=2)}

    def import_bank_statement(
        self,
        financial_year_id: str,
        source: Path,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        try:
            with source.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                bank_rows = list(reader)
        except OSError as exc:
            raise ValidationError(f"Could not read bank file: {exc}") from exc
        if not bank_rows:
            raise ValidationError("Bank file is empty")
        matches: list[dict[str, Any]] = []
        unmatched: list[dict[str, Any]] = []
        with self.databases.connect(self.database_path) as connection:
            for index, row in enumerate(bank_rows, start=2):
                amount_str = (
                    row.get("credit") or row.get("deposit") or row.get("withdrawal")
                    or row.get("debit") or row.get("amount") or "0"
                )
                amount_str = str(amount_str).replace(",", "").strip()
                try:
                    amount_rupees = Decimal(amount_str)
                except Exception:
                    unmatched.append({"row": index, "reason": "Invalid amount"})
                    continue
                amount_paise = int(abs(amount_rupees) * 100)
                txn_date = str(row.get("date") or row.get("txn_date") or "")[:10]
                narration = str(row.get("narration") or row.get("description") or "")
                hit = connection.execute(
                    """
                    SELECT v.voucher_number, vl.debit_paise, vl.credit_paise
                    FROM voucher v
                    JOIN voucher_line vl ON vl.voucher_id = v.voucher_id
                    WHERE v.financial_year_id = ? AND v.voucher_date = ?
                        AND (vl.debit_paise = ? OR vl.credit_paise = ?)
                    LIMIT 1
                    """,
                    (financial_year_id, txn_date, amount_paise, amount_paise),
                ).fetchone()
                entry = {
                    "row": index,
                    "date": txn_date,
                    "narration": narration,
                    "amount_paise": amount_paise,
                }
                if hit:
                    entry["matched_voucher"] = str(hit["voucher_number"])
                    matches.append(entry)
                else:
                    unmatched.append(entry)
        return {
            "dry_run": dry_run,
            "matched": matches,
            "unmatched": unmatched,
            "matched_count": len(matches),
            "unmatched_count": len(unmatched),
        }

    def attach_file(self, document_id: str, source: Path) -> dict[str, str]:
        if not source.is_file():
            raise ValidationError("Attachment file not found")
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        attachment_id = str(uuid.uuid4())
        dest = self.attachments_dir / f"{attachment_id}_{source.name}"
        shutil.copy2(source, dest)
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            doc = connection.execute(
                "SELECT 1 FROM document WHERE document_id = ?", (document_id,)
            ).fetchone()
            if doc is None:
                raise ValidationError("Document not found")
            connection.execute(
                """
                INSERT INTO document_attachment(
                    attachment_id, document_id, file_name, stored_path,
                    mime_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment_id,
                    document_id,
                    source.name,
                    str(dest),
                    "",
                    timestamp,
                ),
            )
        return {"attachment_id": attachment_id, "path": str(dest)}

    def list_attachments(self, document_id: str) -> list[dict[str, str]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT attachment_id, file_name, stored_path, created_at
                FROM document_attachment
                WHERE document_id = ?
                ORDER BY created_at DESC
                """,
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def reminder_letters_pdf(
        self,
        financial_year_id: str,
        as_of_date: str,
        destination: Path,
        *,
        company_name: str,
    ) -> Path:
        with self.databases.connect(self.database_path) as connection:
            parties = connection.execute(
                """
                SELECT p.party_id, p.name, p.address, p.city,
                    SUM(d.balance_paise) AS due_paise
                FROM document d
                JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ? AND d.status = 'posted'
                    AND d.balance_paise > 0 AND d.document_date <= ?
                GROUP BY p.party_id, p.name, p.address, p.city
                ORDER BY p.name
                """,
                (financial_year_id, as_of_date),
            ).fetchall()
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(destination), pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"<b>{company_name}</b>", styles["Title"]),
            Paragraph("<b>Outstanding Payment Reminders</b>", styles["Heading2"]),
            Spacer(1, 12),
        ]
        for row in parties:
            due = int(row["due_paise"])
            story.append(
                Paragraph(
                    f"<b>{row['name']}</b><br/>"
                    f"{row['address'] or ''} {row['city'] or ''}<br/>"
                    f"Total outstanding: ₹{due / 100:,.2f} as on {as_of_date}.<br/>"
                    f"Please remit at the earliest.<br/><br/>",
                    styles["Normal"],
                )
            )
        doc.build(story)
        return destination

    def print_cover(self, party_id: str, destination: Path, *, company_name: str) -> Path:
        with self.databases.connect(self.database_path) as connection:
            party = connection.execute(
                "SELECT name, address, city, phone FROM party WHERE party_id = ?",
                (party_id,),
            ).fetchone()
        if party is None:
            raise ValidationError("Party not found")
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(destination), pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"From:<br/><b>{company_name}</b>", styles["Normal"]),
            Spacer(1, 40),
            Paragraph(
                f"To:<br/><b>{party['name']}</b><br/>"
                f"{party['address'] or ''}<br/>"
                f"{party['city'] or ''}<br/>"
                f"{party['phone'] or ''}",
                styles["Normal"],
            ),
        ]
        doc.build(story)
        return destination
