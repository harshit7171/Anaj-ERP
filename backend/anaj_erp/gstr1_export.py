"""Build GSTR-1 JSON export (B2B, B2C, RCM, CDN, HSN, doc_issue)."""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .database import DatabaseManager
from .gstr1_schema import empty_gstr1_payload
from .gstr1_validate import validate_gstr1_payload
from .gst_document_issue import GstDocumentIssueService
from .gst_report_filters import sale_document_types
from .hsn_apportionment import build_hsn_summary_from_documents
from .hsn_apportionment import load_apportioned_documents_for_period

B2CL_THRESHOLD_PAISE = 25_000_000  # ₹2.5 lakh
NOTE_TYPES = ("gst_credit_note", "gst_debit_note")
INVOICE_TYPES = tuple(t for t in sale_document_types(include_dn_cn=False) if t not in NOTE_TYPES)


def _format_idt(iso_date: str) -> str:
    parts = str(iso_date or "").split("-")
    if len(parts) != 3:
        return str(iso_date)
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


def _fp_from_date(date_from: str) -> str:
    if len(date_from) >= 7:
        return f"{date_from[5:7]}{date_from[:4]}"
    return ""


def _rupees(paise: int) -> float:
    return float(
        (Decimal(int(paise)) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def _effective_rate(taxable_paise: int, tax_paise: int) -> float:
    if taxable_paise <= 0:
        return 0.0
    rate = (Decimal(tax_paise) * Decimal(100) / Decimal(taxable_paise)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return float(rate)


def _itm_from_taxes(taxable_paise: int, tax_parts: dict[str, int]) -> dict[str, Any]:
    total_tax = sum(tax_parts.values())
    return {
        "num": 1,
        "itm_det": {
            "txval": _rupees(taxable_paise),
            "rt": _effective_rate(taxable_paise, total_tax),
            "iamt": _rupees(tax_parts.get("iamt", 0)),
            "camt": _rupees(tax_parts.get("camt", 0)),
            "samt": _rupees(tax_parts.get("samt", 0)),
            "csamt": _rupees(tax_parts.get("csamt", 0)),
        },
    }


def _tax_parts_from_charges(charges: list[dict[str, Any]]) -> dict[str, int]:
    parts = {"iamt": 0, "camt": 0, "samt": 0, "csamt": 0}
    for charge in charges:
        if not charge.get("is_tax"):
            continue
        code = str(charge.get("code") or "").upper()
        amount = int(charge.get("final_amount_paise") or 0)
        if code.startswith("IGST"):
            parts["iamt"] += amount
        elif code.startswith("CGST"):
            parts["camt"] += amount
        elif code.startswith("SGST"):
            parts["samt"] += amount
        elif "CESS" in code:
            parts["csamt"] += amount
    return parts


def _metadata_bool(raw: object) -> bool:
    return str(raw or "").strip().upper() in {"Y", "YES", "1", "TRUE"}


def _reverse_charge(row: dict[str, Any]) -> bool:
    meta = json.loads(str(row.get("header_metadata_json") or "{}"))
    if _metadata_bool(meta.get("rcm") or meta.get("rchrg") or meta.get("reverse_charge")):
        return True
    if _metadata_bool(row.get("party_rcm")):
        return True
    return False


class Gstr1ExportService:
    """Assemble GSTR-1 JSON from posted sale documents."""

    def __init__(self, databases: DatabaseManager, database_path: str) -> None:
        self.databases = databases
        self.database_path = database_path

    def build(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        *,
        validate: bool = True,
    ) -> dict[str, Any]:
        gstin, supplier_state = self._company_identity()
        payload = empty_gstr1_payload(gstin, _fp_from_date(date_from))
        documents = self._load_outward_documents(financial_year_id, date_from, date_to)
        notes = [row for row in documents if str(row["document_type"]) in NOTE_TYPES]
        invoices = [row for row in documents if str(row["document_type"]) not in NOTE_TYPES]

        gt_paise = 0
        b2b_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        b2cl_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        b2cs_map: dict[tuple[str, float], dict[str, int]] = defaultdict(
            lambda: {"txval": 0, "iamt": 0, "camt": 0, "samt": 0, "csamt": 0}
        )

        for row in invoices:
            gstin_party = str(row.get("gstin") or "").strip().upper()
            pos = str(row.get("party_state_code") or supplier_state or "06").zfill(2)[:2]
            taxable = int(row.get("taxable_paise") or row.get("subtotal_paise") or 0)
            grand = int(row.get("grand_total_paise") or 0)
            gt_paise += grand
            tax_parts = row.get("tax_parts") or {}
            inv_item = {
                "inum": str(row["document_number"]),
                "idt": _format_idt(str(row["document_date"])),
                "val": _rupees(grand),
                "pos": pos,
                "rchrg": "Y" if _reverse_charge(row) else "N",
                "inv_typ": "R",
                "itms": [_itm_from_taxes(taxable, tax_parts)],
            }
            if gstin_party:
                b2b_map[gstin_party].append(inv_item)
                continue
            inter_state = pos != (supplier_state or "06").zfill(2)[:2]
            if inter_state and grand > B2CL_THRESHOLD_PAISE:
                b2cl_map[pos].append(
                    {
                        "inum": inv_item["inum"],
                        "idt": inv_item["idt"],
                        "val": inv_item["val"],
                        "itms": inv_item["itms"],
                    }
                )
            else:
                rate = _effective_rate(taxable, sum(tax_parts.values()))
                key = (pos, rate)
                bucket = b2cs_map[key]
                bucket["txval"] += taxable
                bucket["iamt"] += tax_parts.get("iamt", 0)
                bucket["camt"] += tax_parts.get("camt", 0)
                bucket["samt"] += tax_parts.get("samt", 0)
                bucket["csamt"] += tax_parts.get("csamt", 0)

        payload["gt"] = _rupees(gt_paise)
        payload["b2b"] = [
            {"ctin": ctin, "inv": inv_list} for ctin, inv_list in sorted(b2b_map.items())
        ]
        payload["b2cl"] = [
            {"pos": pos, "inv": inv_list} for pos, inv_list in sorted(b2cl_map.items())
        ]
        payload["b2cs"] = [
            {
                "sply_ty": "INTRA" if pos == (supplier_state or "06").zfill(2)[:2] else "INTER",
                "pos": pos,
                "typ": "OE",
                "rt": rate,
                "txval": _rupees(values["txval"]),
                "iamt": _rupees(values["iamt"]),
                "camt": _rupees(values["camt"]),
                "samt": _rupees(values["samt"]),
                "csamt": _rupees(values["csamt"]),
            }
            for (pos, rate), values in sorted(b2cs_map.items())
        ]

        payload["cdnr"] = self._build_cdnr(notes, supplier_state)
        payload["cdnur"] = self._build_cdnur(notes, supplier_state)

        with self.databases.connect(self.database_path) as connection:
            apportioned = load_apportioned_documents_for_period(
                connection,
                financial_year_id,
                date_from,
                date_to,
                INVOICE_TYPES + NOTE_TYPES,
            )
        hsn_buckets = build_hsn_summary_from_documents(apportioned)
        payload["hsn"]["data"] = [
            {
                "num": index + 1,
                "hsn_sc": str(row["hsn_code"]),
                "desc": str(row["description"])[:30],
                "uqc": str(row["uqc"]),
                "qty": float(row["quantity"]),
                "rt": _effective_rate(
                    int(row["taxable_value_paise"]),
                    int(row["igst_paise"])
                    + int(row["cgst_paise"])
                    + int(row["sgst_paise"]),
                ),
                "txval": _rupees(int(row["taxable_value_paise"])),
                "iamt": _rupees(int(row["igst_paise"])),
                "camt": _rupees(int(row["cgst_paise"])),
                "samt": _rupees(int(row["sgst_paise"])),
                "csamt": _rupees(int(row["cess_paise"])),
            }
            for index, row in enumerate(hsn_buckets)
            if str(row.get("hsn_code"))
        ]

        issue_service = GstDocumentIssueService(self.databases, self.database_path)
        issue_rows = issue_service.list_rows(financial_year_id, date_from, date_to)
        payload["doc_issue"]["doc_det"] = self._doc_issue_section(issue_rows)

        payload["period_from"] = date_from
        payload["period_to"] = date_to
        payload["generated_from"] = "AnajERP-offline"

        if validate and gstin:
            from .gstr1_validate import validate_gstr1_offline_utility

            validate_gstr1_offline_utility(payload)
        return payload

    def _company_identity(self) -> tuple[str, str]:
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT gstin, state_code FROM company LIMIT 1"
            ).fetchone()
        if row is None:
            return "", "06"
        return str(row["gstin"] or "").strip().upper(), str(row["state_code"] or "06")

    def _load_outward_documents(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        types = sale_document_types(include_dn_cn=True)
        placeholders = ",".join("?" for _ in types)
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_id, d.document_type, d.document_number, d.document_date,
                    d.subtotal_paise, d.grand_total_paise, d.reference_number,
                    d.header_metadata_json,
                    p.name AS party_name, p.gstin, p.state_code AS party_state_code,
                    json_extract(COALESCE(a.metadata_json, '{{}}'), '$.rcm_purchase') AS party_rcm
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                LEFT JOIN account a ON a.account_id = p.account_id
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
                charge_placeholders = ",".join("?" for _ in doc_ids)
                charge_rows = connection.execute(
                    f"""
                    SELECT document_id, code, final_amount_paise, is_tax, rate_decimal
                    FROM document_charge
                    WHERE document_id IN ({charge_placeholders})
                    """,
                    tuple(doc_ids),
                ).fetchall()
                for charge in charge_rows:
                    charges_by_doc[str(charge["document_id"])].append(dict(charge))
            orig_dates = self._original_invoice_dates(connection, rows)

        output: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            doc_id = str(payload["document_id"])
            charges = charges_by_doc.get(doc_id, [])
            tax_parts = _tax_parts_from_charges(charges)
            payload["tax_parts"] = tax_parts
            payload["taxable_paise"] = int(payload.get("subtotal_paise") or 0)
            payload["orig_invoice_date"] = orig_dates.get(doc_id, "")
            output.append(payload)
        return output

    def _original_invoice_dates(
        self,
        connection: Any,
        rows: list[Any],
    ) -> dict[str, str]:
        refs = {
            str(row["reference_number"]): str(row["document_id"])
            for row in rows
            if str(row.get("reference_number") or "").strip()
        }
        if not refs:
            return {}
        placeholders = ",".join("?" for _ in refs)
        found = connection.execute(
            f"""
            SELECT document_number, document_date
            FROM document
            WHERE document_number IN ({placeholders}) AND status = 'posted'
            """,
            tuple(refs.keys()),
        ).fetchall()
        by_number = {str(r["document_number"]): str(r["document_date"]) for r in found}
        out: dict[str, str] = {}
        for ref, doc_id in refs.items():
            out[doc_id] = by_number.get(ref, "")
        return out

    def _build_cdnr(
        self,
        notes: list[dict[str, Any]],
        supplier_state: str,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in notes:
            gstin_party = str(row.get("gstin") or "").strip().upper()
            if not gstin_party:
                continue
            meta = json.loads(str(row.get("header_metadata_json") or "{}"))
            orig_num = str(row.get("reference_number") or meta.get("ref_no") or meta.get("orig_inum") or "")
            orig_dt = _format_idt(
                str(row.get("orig_invoice_date") or meta.get("orig_idt") or row.get("document_date"))
            )
            note_type = "C" if str(row["document_type"]) == "gst_credit_note" else "D"
            taxable = int(row.get("taxable_paise") or 0)
            grouped[gstin_party].append(
                {
                    "ntty": note_type,
                    "nt_num": str(row["document_number"]),
                    "nt_dt": _format_idt(str(row["document_date"])),
                    "p_gst": "N",
                    "inum": orig_num,
                    "idt": orig_dt,
                    "val": _rupees(int(row.get("grand_total_paise") or 0)),
                    "itms": [_itm_from_taxes(taxable, row.get("tax_parts") or {})],
                }
            )
        return [{"ctin": ctin, "nt": nt_list} for ctin, nt_list in sorted(grouped.items())]

    def _build_cdnur(
        self,
        notes: list[dict[str, Any]],
        supplier_state: str,
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for row in notes:
            if str(row.get("gstin") or "").strip():
                continue
            meta = json.loads(str(row.get("header_metadata_json") or "{}"))
            orig_num = str(row.get("reference_number") or meta.get("ref_no") or "")
            orig_dt = _format_idt(
                str(row.get("orig_invoice_date") or meta.get("orig_idt") or row.get("document_date"))
            )
            pos = str(row.get("party_state_code") or supplier_state or "06").zfill(2)[:2]
            note_type = "C" if str(row["document_type"]) == "gst_credit_note" else "D"
            taxable = int(row.get("taxable_paise") or 0)
            output.append(
                {
                    "typ": "B2CL" if pos != supplier_state.zfill(2)[:2] else "B2CS",
                    "ntty": note_type,
                    "nt_num": str(row["document_number"]),
                    "nt_dt": _format_idt(str(row["document_date"])),
                    "p_gst": "N",
                    "inum": orig_num,
                    "idt": orig_dt,
                    "val": _rupees(int(row.get("grand_total_paise") or 0)),
                    "itms": [_itm_from_taxes(taxable, row.get("tax_parts") or {})],
                }
            )
        return output

    @staticmethod
    def _doc_issue_section(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_nature: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_nature[str(row["gst_nature"])].append(row)
        doc_det: list[dict[str, Any]] = []
        for doc_num, (nature, items) in enumerate(sorted(by_nature.items()), start=1):
            docs = []
            for num, item in enumerate(items, start=1):
                docs.append(
                    {
                        "num": num,
                        "from": str(item["serial_from"]),
                        "to": str(item["serial_to"]),
                        "totnum": int(item["total_count"]),
                        "cancel": int(item["cancelled_count"]),
                        "net_issue": int(item.get("net_issued") or item["total_count"]),
                    }
                )
            doc_det.append({"doc_num": doc_num, "doc_typ": nature, "docs": docs})
        return doc_det
