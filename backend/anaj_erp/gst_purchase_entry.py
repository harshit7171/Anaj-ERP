"""Normal GST purchase entry add/modify."""

from __future__ import annotations

import json
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .documents import DocumentService
from .errors import ValidationError

DOCUMENT_TYPE = "gst_purchase"


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception as exc:
        raise ValidationError("Invalid number") from exc


def _money_paise(value: Any) -> int:
    return int((_dec(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _net_weight(gross: Decimal, tare: Decimal, adj: Decimal) -> Decimal:
    net = gross - tare + adj
    return net if net > 0 else Decimal("0")


def _line_taxable(net: Decimal, rate: Decimal, qty: Decimal) -> Decimal:
    if net > 0:
        return (net * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if qty > 0:
        return (qty * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal("0")


class GstPurchaseEntryService:
    """Legacy GST purchase with rate/expense panels and weight grid."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.documents = DocumentService(databases, company_id)

    def get_gst_purchase_entry(
        self,
        financial_year_id: str,
        *,
        document_id: str = "",
        entry_date: str = "",
        party_id: str = "",
        bill_no: str = "",
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            row = None
            clean_id = str(document_id or "").strip()
            if clean_id:
                row = connection.execute(
                    """
                    SELECT d.*, p.name AS party_name, p.gstin AS party_gstin
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.document_id = ? AND d.document_type = ?
                    """,
                    (clean_id, DOCUMENT_TYPE),
                ).fetchone()
            else:
                if not entry_date.strip() or not party_id.strip():
                    raise ValidationError("Date and Party A/c are required to find an entry")
                params: list[Any] = [
                    financial_year_id,
                    DOCUMENT_TYPE,
                    entry_date.strip(),
                    party_id.strip(),
                ]
                bill_sql = ""
                if bill_no.strip():
                    bill_sql = " AND (d.reference_number = ? OR d.document_number = ?)"
                    params.extend([bill_no.strip(), bill_no.strip()])
                row = connection.execute(
                    f"""
                    SELECT d.*, p.name AS party_name, p.gstin AS party_gstin
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type = ?
                      AND d.document_date = ?
                      AND d.party_id = ?
                    {bill_sql}
                    ORDER BY d.updated_at DESC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
            if row is None:
                raise ValidationError("GST purchase entry not found")
            document_id = str(row["document_id"])
            lines = connection.execute(
                """
                SELECT dl.*, co.name AS commodity_name
                FROM document_line dl
                JOIN commodity co ON co.commodity_id = dl.commodity_id
                WHERE dl.document_id = ?
                ORDER BY dl.line_number
                """,
                (document_id,),
            ).fetchall()
        meta = json.loads(str(row["header_metadata_json"] or "{}"))
        payload = self._header_to_form(dict(row), meta)
        payload["lines"] = []
        for line in lines:
            item = dict(line)
            item["metadata"] = json.loads(str(item.get("line_metadata_json") or "{}"))
            payload["lines"].append(self._line_to_form(item))
        payload["expenses"] = list(meta.get("expenses") or [])
        payload["rate_rows"] = list(meta.get("rate_rows") or [])
        return payload

    def save_gst_purchase_entry(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        document_id = str(payload.get("document_id") or "").strip()
        if document_id:
            self.delete_gst_purchase_entry(financial_year_id, document_id)
        party_id = str(payload.get("party_id") or "").strip()
        if not party_id:
            raise ValidationError("Party A/c is required")
        entry_date = str(payload.get("entry_date") or "").strip()
        if not entry_date:
            raise ValidationError("Date is required")
        bill_no = str(payload.get("bill_no") or "").strip()
        document_number = str(payload.get("document_number") or "").strip() or bill_no
        if not document_number:
            document_number = self.documents.next_document_number(
                financial_year_id,
                DOCUMENT_TYPE,
            )
        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ValidationError("At least one line is required")
        document_lines: list[dict[str, Any]] = []
        for raw in raw_lines:
            if not isinstance(raw, dict):
                continue
            commodity_id = str(raw.get("commodity_id") or "").strip()
            if not commodity_id:
                continue
            qty = _dec(raw.get("qty"))
            gross = _dec(raw.get("gross_wt"))
            tare = _dec(raw.get("tare"))
            adj = _dec(raw.get("adj_wt"))
            net = _dec(raw.get("net_wt")) if raw.get("net_wt") else _net_weight(gross, tare, adj)
            rate = _dec(raw.get("rate"))
            if net <= 0 and qty <= 0:
                continue
            taxable = _line_taxable(net, rate, qty)
            cgst = _dec(raw.get("cgst_pct"))
            sgst = _dec(raw.get("sgst_pct"))
            igst = _dec(raw.get("igst_pct"))
            gst_amt = (taxable * (cgst + sgst + igst) / Decimal("100")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            document_lines.append(
                {
                    "commodity_id": commodity_id,
                    "description": str(raw.get("item_desc") or raw.get("item_name") or "Item"),
                    "hsn_code": str(raw.get("hsn_code") or ""),
                    "bags_scaled": int(qty.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                    "bag_scale": 0,
                    "packing_weight_scaled": int(gross * 1000) if gross else 0,
                    "loose_quantity_scaled": 0,
                    "quantity_scaled": int((net if net > 0 else qty) * 1000),
                    "quantity_scale": 3,
                    "rate_paise": _money_paise(rate),
                    "rate_unit": "quintal",
                    "metadata": {
                        **raw,
                        "item_name": raw.get("item_name"),
                        "item_desc": raw.get("item_desc"),
                        "taxable": str(taxable),
                        "amount": str(taxable),
                        "gst_amt": str(gst_amt),
                        "net_wt": str(net),
                    },
                }
            )
        if not document_lines:
            raise ValidationError("At least one valid line is required")
        header_meta = {k: v for k, v in payload.items() if k not in {"lines", "document_id"}}
        header_meta["expenses"] = payload.get("expenses") or []
        header_meta["rate_rows"] = payload.get("rate_rows") or []
        with self.databases.connect(self.database_path) as connection:
            main_account_id, party_account_id = self._resolve_accounts(connection, party_id)
        header = {
            "reference_number": bill_no,
            "due_date": str(payload.get("due_date") or ""),
            "vehicle_number": str(payload.get("veh_no") or ""),
            "gr_number": str(payload.get("gr_no") or ""),
            "gr_date": str(payload.get("gr_date") or ""),
            "eway_bill_number": str(payload.get("eway_no") or ""),
            "from_place": str(payload.get("dispatch") or ""),
            "remarks": str(payload.get("remarks") or ""),
            "freight_paise": _money_paise(payload.get("freight") or 0),
            "metadata": header_meta,
        }
        posted = self.documents.post(
            financial_year_id=financial_year_id,
            document_type=DOCUMENT_TYPE,
            document_number=document_number,
            document_date=entry_date,
            party_id=party_id,
            main_account_id=main_account_id,
            party_account_id=party_account_id,
            lines=document_lines,
            header=header,
        )
        return self.get_gst_purchase_entry(financial_year_id, document_id=str(posted["document_id"]))

    def delete_gst_purchase_entry(self, financial_year_id: str, document_id: str) -> dict[str, str]:
        clean = str(document_id or "").strip()
        if not clean:
            raise ValidationError("Document id is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT posted_voucher_id, document_date, document_number
                FROM document WHERE document_id = ? AND financial_year_id = ? AND document_type = ?
                """,
                (clean, financial_year_id, DOCUMENT_TYPE),
            ).fetchone()
            if row is None:
                raise ValidationError("GST purchase entry not found")
            voucher_id = str(row["posted_voucher_id"] or "")
            document_date = str(row["document_date"])
            document_number = str(row["document_number"])
        if voucher_id:
            AccountingService(self.databases, self.company_id).reverse_voucher(
                voucher_id,
                f"REV-{document_number}"[:24],
                document_date,
                "GST purchase modify or delete",
            )
        with self.databases.connect(self.database_path) as connection:
            connection.execute("DELETE FROM inventory_movement WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document_charge WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document_line WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document WHERE document_id = ?", (clean,))
        return {"document_id": clean}

    def lookup_items(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT commodity_id, name, variety, hsn_code
                FROM commodity
                WHERE is_deleted = 0 AND (name LIKE ? OR variety LIKE ?)
                ORDER BY name COLLATE NOCASE LIMIT 40
                """,
                (pattern, pattern),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            name = str(row["name"] or "")
            variety = str(row["variety"] or "").strip()
            item_name = f"{name} {variety}".strip() if variety else name
            out.append(
                {
                    "commodity_id": row["commodity_id"],
                    "item_name": item_name,
                    "hsn_code": row["hsn_code"] or "",
                    "unit": "Qtls",
                }
            )
        return out

    def lookup_parties(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT party_id, name, gstin, city
                FROM party WHERE is_deleted = 0 AND name LIKE ?
                ORDER BY name COLLATE NOCASE LIMIT 40
                """,
                (pattern,),
            ).fetchall()
        return [dict(row) for row in rows]

    def lookup_purchase_accounts(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT account_id, name FROM account
                WHERE is_deleted = 0 AND account_type IN ('expense', 'purchase')
                  AND name LIKE ?
                ORDER BY name COLLATE NOCASE LIMIT 30
                """,
                (pattern,),
            ).fetchall()
        return [{"account_id": r["account_id"], "account_name": r["name"]} for r in rows]

    def next_entry_number(self, financial_year_id: str) -> str:
        return self.documents.next_document_number(financial_year_id, DOCUMENT_TYPE)

    @staticmethod
    def _resolve_accounts(connection: Any, party_id: str) -> tuple[str, str]:
        party = connection.execute(
            "SELECT account_id FROM party WHERE party_id = ? AND is_deleted = 0",
            (party_id,),
        ).fetchone()
        if party is None or not party["account_id"]:
            raise ValidationError("Party must have a linked ledger account")
        party_account_id = str(party["account_id"])
        main = connection.execute(
            """
            SELECT account_id FROM account
            WHERE is_deleted = 0 AND account_type IN ('expense', 'purchase')
              AND (name LIKE '%GST%' OR name LIKE '%Purchase%')
            ORDER BY name COLLATE NOCASE LIMIT 1
            """
        ).fetchone()
        if main is None:
            main = connection.execute(
                """
                SELECT account_id FROM account
                WHERE is_deleted = 0 AND account_type = 'expense'
                ORDER BY name COLLATE NOCASE LIMIT 1
                """
            ).fetchone()
        if main is None:
            raise ValidationError("Create a Purchase/GST expense account before posting")
        return str(main["account_id"]), party_account_id

    @staticmethod
    def _header_to_form(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        base = {
            "document_id": row["document_id"],
            "document_number": row["document_number"],
            "entry_date": row["document_date"],
            "party_id": row.get("party_id") or "",
            "party_name": row.get("party_name") or "",
            "party_gstin": row.get("party_gstin") or "",
            "bill_no": meta.get("bill_no") or row.get("reference_number") or "",
        }
        for key, value in meta.items():
            if key not in base:
                base[key] = value
        return base

    @staticmethod
    def _line_to_form(row: dict[str, Any]) -> dict[str, Any]:
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        scale = int(row.get("quantity_scale") or 3)
        net = Decimal(str(row.get("quantity_scaled") or 0)) / (Decimal(10) ** scale)
        rate = Decimal(int(row.get("rate_paise") or 0)) / Decimal(100)
        taxable = Decimal(str(meta.get("taxable") or meta.get("amount") or net * rate))
        return {
            "commodity_id": row.get("commodity_id"),
            "item_name": meta.get("item_name") or row.get("commodity_name") or "",
            "item_desc": meta.get("item_desc") or meta.get("item_name") or "",
            "purchase_ac": meta.get("purchase_ac") or "",
            "purchase_ac_id": meta.get("purchase_ac_id") or "",
            "unit": meta.get("unit") or "Qtls",
            "sauda_no": meta.get("sauda_no") or "",
            "qty": meta.get("qty") or str(row.get("bags_scaled") or ""),
            "bharti": meta.get("bharti") or "",
            "gross_wt": meta.get("gross_wt") or "",
            "tare": meta.get("tare") or "",
            "adj_wt": meta.get("adj_wt") or "",
            "net_wt": meta.get("net_wt") or f"{net:.3f}",
            "nw": meta.get("nw") or "N",
            "rate": meta.get("rate") or f"{rate:.2f}",
            "amount": meta.get("amount") or f"{taxable:.2f}",
            "hsn_code": meta.get("hsn_code") or row.get("hsn_code") or "",
            "gst_adj": meta.get("gst_adj") or "",
            "cgst_pct": meta.get("cgst_pct") or "",
            "sgst_pct": meta.get("sgst_pct") or "",
            "igst_pct": meta.get("igst_pct") or "",
            "gst_amt": meta.get("gst_amt") or "0.00",
        }
