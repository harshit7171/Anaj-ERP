"""GSTR-2B import and reconciliation against purchase books."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .database import DatabaseManager
from .errors import ValidationError
from .gst_report_filters import purchase_document_types
from .gstr2b_ingest import parse_gstr2b_json
from .gstr2b_ingest import summarize_gstr2b
from .gstr2b_matching import LocalPurchaseInvoice
from .gstr2b_matching import STATUS_LABELS
from .gstr2b_matching import suggested_action
from .gstr2b_matching import match_gstr2b_to_books
from .gstr1_export import _tax_parts_from_charges


class Gstr2bReconciliationService:
    """Load portal JSON and match to local purchase vouchers."""

    def __init__(self, databases: DatabaseManager, database_path: str) -> None:
        self.databases = databases
        self.database_path = database_path

    def load_json_file(self, path: str) -> dict[str, Any]:
        file_path = Path(str(path).strip())
        if not file_path.is_file():
            raise ValidationError("GSTR-2B JSON file not found")
        raw = file_path.read_text(encoding="utf-8")
        records = parse_gstr2b_json(raw)
        return {"records": records, "summary": summarize_gstr2b(records), "file_path": str(file_path)}

    def load_json_text(self, json_text: str) -> dict[str, Any]:
        records = parse_gstr2b_json(json_text)
        return {"records": records, "summary": summarize_gstr2b(records)}

    def local_purchases(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[LocalPurchaseInvoice]:
        types = purchase_document_types(include_dn_cn=True, include_expense=True)
        placeholders = ",".join("?" for _ in types)
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_id, d.document_number, d.document_date,
                    d.subtotal_paise, d.grand_total_paise,
                    p.name AS party_name, p.gstin
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                  AND d.status = 'posted'
                  AND d.document_date BETWEEN ? AND ?
                  AND d.document_type IN ({placeholders})
                ORDER BY d.document_date, d.document_number
                """,
                (financial_year_id, date_from, date_to, *types),
            ).fetchall()
            doc_ids = [str(row["document_id"]) for row in rows]
            charges_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if doc_ids:
                charge_ph = ",".join("?" for _ in doc_ids)
                for charge in connection.execute(
                    f"""
                    SELECT document_id, code, final_amount_paise, is_tax
                    FROM document_charge WHERE document_id IN ({charge_ph})
                    """,
                    tuple(doc_ids),
                ).fetchall():
                    charges_by_doc[str(charge["document_id"])].append(dict(charge))

        output: list[LocalPurchaseInvoice] = []
        for row in rows:
            doc_id = str(row["document_id"])
            tax = _tax_parts_from_charges(charges_by_doc.get(doc_id, []))
            gstin = str(row["gstin"] or "").strip().upper()
            if not gstin:
                continue
            output.append(
                LocalPurchaseInvoice(
                    document_id=doc_id,
                    supplier_gstin=gstin,
                    invoice_number=str(row["document_number"]),
                    invoice_date=str(row["document_date"]),
                    invoice_value_paise=int(row["grand_total_paise"] or 0),
                    taxable_paise=int(row["subtotal_paise"] or 0),
                    igst_paise=tax.get("iamt", 0),
                    cgst_paise=tax.get("camt", 0),
                    sgst_paise=tax.get("samt", 0),
                    cess_paise=tax.get("csamt", 0),
                    party_name=str(row["party_name"] or ""),
                )
            )
        return output

    def reconcile(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        portal_records: list[Any],
        *,
        tolerance_paise: int = 100,
    ) -> dict[str, Any]:
        local_rows = self.local_purchases(financial_year_id, date_from, date_to)
        return match_gstr2b_to_books(
            portal_records,
            local_rows,
            tolerance_paise=tolerance_paise,
        )

    def reconcile_from_file(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        file_path: str,
        *,
        tolerance_paise: int = 100,
    ) -> dict[str, Any]:
        loaded = self.load_json_file(file_path)
        matched = self.reconcile(
            financial_year_id,
            date_from,
            date_to,
            loaded["records"],
            tolerance_paise=tolerance_paise,
        )
        matched["portal_summary"] = loaded["summary"]
        matched["file_path"] = loaded["file_path"]
        return matched

    @staticmethod
    def _rupees(paise: int) -> str:
        return f"{paise / 100:.2f}"

    @classmethod
    def display_rows(cls, reconcile_result: dict[str, Any]) -> list[dict[str, str]]:
        display: list[dict[str, str]] = []
        for row in reconcile_result.get("rows") or []:
            bucket = str(row.get("status_bucket") or "")
            label = STATUS_LABELS.get(bucket, bucket or "—")
            doc_id = str(row.get("document_id") or "")
            display.append(
                {
                    "status_bucket": bucket,
                    "Status": label,
                    "Suggested Action": suggested_action(bucket, doc_id),
                    "Document Id": doc_id,
                    "Match Tier": str(row.get("match_tier") or "—"),
                    "Supplier GSTIN": str(row.get("supplier_gstin") or ""),
                    "Trade Name": str(row.get("party_name") or ""),
                    "2B Invoice No": str(row.get("portal_invoice_no") or ""),
                    "Books Invoice No": str(row.get("books_invoice_no") or ""),
                    "2B Date": str(row.get("portal_invoice_date") or ""),
                    "Books Date": str(row.get("books_invoice_date") or ""),
                    "2B Taxable": cls._rupees(int(row.get("portal_taxable") or 0)),
                    "Books Taxable": cls._rupees(int(row.get("books_taxable") or 0)),
                    "2B Tax": cls._rupees(int(row.get("portal_tax") or 0)),
                    "Books Tax": cls._rupees(int(row.get("books_tax") or 0)),
                    "Tax Diff (₹)": cls._rupees(int(row.get("tax_diff_paise") or 0)),
                }
            )
        return display
