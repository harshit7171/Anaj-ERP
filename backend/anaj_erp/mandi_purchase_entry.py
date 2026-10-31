"""Mandi purchase entry (Pakki purchase) add/modify screen."""

from __future__ import annotations

import json
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .documents import DocumentService
from .errors import ValidationError

DOCUMENT_TYPE = "mandi_purchase"


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception as exc:
        raise ValidationError("Invalid number") from exc


def _money_paise(value: Any) -> int:
    return int((_dec(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _line_amount(weight: Decimal, rate: Decimal, round_off: bool) -> Decimal:
    raw = weight * rate
    if round_off:
        return raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class MandiPurchaseEntryService:
    """Legacy mandi purchase with item grid, transport and bardana tabs."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.documents = DocumentService(databases, company_id)

    def get_mandi_purchase_entry(
        self,
        financial_year_id: str,
        *,
        document_id: str = "",
        entry_date: str = "",
        purchase_party_id: str = "",
        document_number: str = "",
        line_bill_no: str = "",
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            row = None
            clean_id = str(document_id or "").strip()
            if clean_id:
                row = connection.execute(
                    """
                    SELECT d.*, p.name AS purchase_party_name
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.document_id = ? AND d.document_type = ?
                    """,
                    (clean_id, DOCUMENT_TYPE),
                ).fetchone()
            else:
                if not entry_date.strip() or not purchase_party_id.strip():
                    raise ValidationError("Date and Purchase A/c are required to find an entry")
                params: list[Any] = [
                    financial_year_id,
                    DOCUMENT_TYPE,
                    entry_date.strip(),
                    purchase_party_id.strip(),
                ]
                number_sql = ""
                if document_number.strip():
                    number_sql = " AND d.document_number = ?"
                    params.append(document_number.strip())
                bill_sql = ""
                if line_bill_no.strip():
                    bill_sql = """
                      AND EXISTS (
                        SELECT 1 FROM document_line dl
                        WHERE dl.document_id = d.document_id
                          AND (
                            dl.source_reference_number = ?
                            OR json_extract(dl.line_metadata_json, '$.bill_no') = ?
                          )
                      )
                    """
                    params.extend([line_bill_no.strip(), line_bill_no.strip()])
                row = connection.execute(
                    f"""
                    SELECT d.*, p.name AS purchase_party_name
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type = ?
                      AND d.document_date = ?
                      AND d.party_id = ?
                    {number_sql}
                    {bill_sql}
                    ORDER BY d.updated_at DESC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
            if row is None:
                raise ValidationError("Mandi purchase entry not found")
            document_id = str(row["document_id"])
            lines = connection.execute(
                """
                SELECT dl.*, co.name AS commodity_name, sp.name AS party_name
                FROM document_line dl
                JOIN commodity co ON co.commodity_id = dl.commodity_id
                LEFT JOIN party sp ON sp.party_id = dl.source_party_id
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
        payload["item_summary"] = list(meta.get("item_summary") or [])
        payload["expenses"] = list(meta.get("expenses") or [])
        payload["transport"] = meta.get("transport") or {}
        payload["bardana"] = meta.get("bardana") or {}
        return payload

    def save_mandi_purchase_entry(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        document_id = str(payload.get("document_id") or "").strip()
        if document_id:
            self.delete_mandi_purchase_entry(financial_year_id, document_id)
        purchase_party_id = str(payload.get("purchase_party_id") or "").strip()
        if not purchase_party_id:
            raise ValidationError("Purchase A/c is required")
        entry_date = str(payload.get("entry_date") or "").strip()
        if not entry_date:
            raise ValidationError("Date is required")
        document_number = str(payload.get("document_number") or "").strip()
        if not document_number:
            document_number = self.documents.next_document_number(
                financial_year_id,
                DOCUMENT_TYPE,
            )
        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ValidationError("At least one item line is required")
        document_lines: list[dict[str, Any]] = []
        for raw in raw_lines:
            if not isinstance(raw, dict):
                continue
            commodity_id = str(raw.get("commodity_id") or "").strip()
            line_party_id = str(raw.get("line_party_id") or "").strip()
            if not commodity_id or not line_party_id:
                continue
            bags = _dec(raw.get("nugs"))
            weight = _dec(raw.get("weight"))
            rate = _dec(raw.get("rate"))
            if weight <= 0:
                continue
            round_off = str(raw.get("r_off") or "N").upper().startswith("Y")
            amount = _line_amount(weight, rate, round_off)
            tds_pct = _dec(raw.get("tds_pct"))
            tds_on = str(raw.get("tds_on") or "N")
            tds_base = amount if tds_on.upper().startswith("Y") else Decimal("0")
            tds_amt = (tds_base * tds_pct / Decimal("100")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            bill_no = str(raw.get("bill_no") or "")
            document_lines.append(
                {
                    "commodity_id": commodity_id,
                    "description": str(raw.get("item_name") or "Commodity"),
                    "source_party_id": line_party_id,
                    "source_reference_number": bill_no,
                    "bags_scaled": int(bags.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                    "bag_scale": 0,
                    "packing_weight_scaled": 0,
                    "loose_quantity_scaled": 0,
                    "quantity_scaled": int(weight * 1000),
                    "quantity_scale": 3,
                    "rate_paise": _money_paise(rate),
                    "rate_unit": "quintal",
                    "metadata": {
                        "party_name": raw.get("party_name"),
                        "bill_no": bill_no,
                        "due_date": raw.get("due_date"),
                        "item_name": raw.get("item_name"),
                        "unit": raw.get("unit"),
                        "nugs": str(bags),
                        "weight": str(weight),
                        "nw": raw.get("nw"),
                        "rate": str(rate),
                        "amount": str(amount),
                        "r_off": raw.get("r_off"),
                        "bill_amt": str(raw.get("bill_amt") or amount),
                        "tds_on": tds_on,
                        "tds_pct": str(tds_pct),
                        "tds_on_amt": raw.get("tds_on_amt"),
                        "tds": str(tds_amt),
                        "ref_code": raw.get("ref_code") or "PU1",
                    },
                }
            )
        if not document_lines:
            raise ValidationError("At least one valid item line is required")
        header_meta = {
            "user_name": payload.get("user_name") or "USER",
            "cash_credit": payload.get("cash_credit") or "Credit",
            "mandi_city": payload.get("mandi_city"),
            "exp_master": payload.get("exp_master"),
            "broker": payload.get("broker"),
            "market_paid": payload.get("market_paid") or "N",
            "pur_type": payload.get("pur_type") or "L",
            "rcm": payload.get("rcm") or "N",
            "gst": payload.get("gst") or "N",
            "header_amount": payload.get("header_amount"),
            "stock_rcvd": payload.get("stock_rcvd") or "N",
            "tds_rate": payload.get("tds_rate"),
            "expenses": payload.get("expenses") or [],
            "item_summary": payload.get("item_summary") or [],
            "transport": payload.get("transport") or {},
            "bardana": payload.get("bardana") or {},
            "totals": payload.get("totals") or {},
        }
        with self.databases.connect(self.database_path) as connection:
            main_account_id, party_account_id = self._resolve_accounts(
                connection,
                purchase_party_id,
            )
        header = {
            "from_place": str(payload.get("mandi_city") or ""),
            "due_date": str(payload.get("due_date") or ""),
            "remarks": str(payload.get("remarks") or ""),
            "metadata": header_meta,
        }
        posted = self.documents.post(
            financial_year_id=financial_year_id,
            document_type=DOCUMENT_TYPE,
            document_number=document_number,
            document_date=entry_date,
            party_id=purchase_party_id,
            main_account_id=main_account_id,
            party_account_id=party_account_id,
            lines=document_lines,
            header=header,
        )
        return self.get_mandi_purchase_entry(
            financial_year_id,
            document_id=str(posted["document_id"]),
        )

    def delete_mandi_purchase_entry(self, financial_year_id: str, document_id: str) -> dict[str, str]:
        clean = str(document_id or "").strip()
        if not clean:
            raise ValidationError("Document id is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT posted_voucher_id, document_date, document_number
                FROM document
                WHERE document_id = ? AND financial_year_id = ? AND document_type = ?
                """,
                (clean, financial_year_id, DOCUMENT_TYPE),
            ).fetchone()
            if row is None:
                raise ValidationError("Mandi purchase entry not found")
            voucher_id = str(row["posted_voucher_id"] or "")
            document_date = str(row["document_date"])
            document_number = str(row["document_number"])
        if voucher_id:
            AccountingService(self.databases, self.company_id).reverse_voucher(
                voucher_id,
                f"REV-{document_number}"[:24],
                document_date,
                "Mandi purchase modify or delete",
            )
        with self.databases.connect(self.database_path) as connection:
            connection.execute("DELETE FROM inventory_movement WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document_charge WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document_line WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document WHERE document_id = ?", (clean,))
        return {"document_id": clean}

    def lookup_parties(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT party_id, name, city
                FROM party WHERE is_deleted = 0 AND name LIKE ?
                ORDER BY name COLLATE NOCASE LIMIT 40
                """,
                (pattern,),
            ).fetchall()
        return [dict(row) for row in rows]

    def lookup_items(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT commodity_id, name, variety
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
            out.append({"commodity_id": row["commodity_id"], "item_name": item_name, "unit": "Qtls"})
        return out

    def lookup_line_rates(
        self,
        financial_year_id: str,
        *,
        line_party_id: str,
        commodity_id: str,
    ) -> list[dict[str, Any]]:
        if not line_party_id or not commodity_id:
            return []
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT dl.rate_paise,
                       SUM(dl.quantity_scaled * 1.0 / POWER(10, dl.quantity_scale)) AS weight
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                WHERE d.financial_year_id = ?
                  AND d.document_type = ?
                  AND dl.source_party_id = ?
                  AND dl.commodity_id = ?
                GROUP BY dl.rate_paise
                ORDER BY d.document_date DESC
                LIMIT 12
                """,
                (financial_year_id, DOCUMENT_TYPE, line_party_id, commodity_id),
            ).fetchall()
        return [
            {
                "rate": f"{int(row['rate_paise']) / 100:.2f}",
                "weight": f"{Decimal(str(row['weight'] or 0)):.3f}",
            }
            for row in rows
        ]

    def next_entry_number(self, financial_year_id: str) -> str:
        return self.documents.next_document_number(financial_year_id, DOCUMENT_TYPE)

    @staticmethod
    def _resolve_accounts(connection: Any, purchase_party_id: str) -> tuple[str, str]:
        party = connection.execute(
            "SELECT account_id FROM party WHERE party_id = ? AND is_deleted = 0",
            (purchase_party_id,),
        ).fetchone()
        if party is None or not party["account_id"]:
            raise ValidationError("Purchase party must have a linked ledger account")
        party_account_id = str(party["account_id"])
        main = connection.execute(
            """
            SELECT account_id FROM account
            WHERE is_deleted = 0 AND account_type IN ('expense', 'purchase')
              AND (name LIKE '%Purchase%' OR name LIKE '%Mandi%')
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
            raise ValidationError("Create a Purchase expense account before posting")
        return str(main["account_id"]), party_account_id

    @staticmethod
    def _header_to_form(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_id": row["document_id"],
            "document_number": row["document_number"],
            "entry_date": row["document_date"],
            "purchase_party_id": row.get("party_id") or "",
            "purchase_party_name": row.get("purchase_party_name") or "",
            "user_name": meta.get("user_name") or "USER",
            "cash_credit": meta.get("cash_credit") or "Credit",
            "mandi_city": meta.get("mandi_city") or row.get("from_place") or "",
            "exp_master": meta.get("exp_master") or "",
            "broker": meta.get("broker") or "",
            "market_paid": meta.get("market_paid") or "N",
            "pur_type": meta.get("pur_type") or "L",
            "rcm": meta.get("rcm") or "N",
            "gst": meta.get("gst") or "N",
            "header_amount": meta.get("header_amount") or "",
            "due_date": row.get("due_date") or "",
            "stock_rcvd": meta.get("stock_rcvd") or "N",
            "tds_rate": meta.get("tds_rate") or "2.00",
            "remarks": row.get("remarks") or "",
            "totals": meta.get("totals") or {},
        }

    @staticmethod
    def _line_to_form(row: dict[str, Any]) -> dict[str, Any]:
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        scale = int(row.get("quantity_scale") or 3)
        weight = Decimal(str(row.get("quantity_scaled") or 0)) / (Decimal(10) ** scale)
        rate = Decimal(int(row.get("rate_paise") or 0)) / Decimal(100)
        return {
            "commodity_id": row.get("commodity_id"),
            "line_party_id": row.get("source_party_id"),
            "party_name": meta.get("party_name") or row.get("party_name") or "",
            "bill_no": meta.get("bill_no") or row.get("source_reference_number") or "",
            "due_date": meta.get("due_date") or "",
            "item_name": meta.get("item_name") or row.get("commodity_name") or "",
            "unit": meta.get("unit") or "Qtls",
            "nugs": meta.get("nugs") or str(row.get("bags_scaled") or ""),
            "weight": meta.get("weight") or f"{weight:.3f}",
            "nw": meta.get("nw") or "N",
            "rate": meta.get("rate") or f"{rate:.2f}",
            "amount": meta.get("amount") or f"{(weight * rate):.2f}",
            "r_off": meta.get("r_off") or "Y",
            "bill_amt": meta.get("bill_amt") or meta.get("amount") or "",
            "tds_on": meta.get("tds_on") or "N",
            "tds_pct": meta.get("tds_pct") or "",
            "tds_on_amt": meta.get("tds_on_amt") or "",
            "tds": meta.get("tds") or "0.00",
            "ref_code": meta.get("ref_code") or "PU1",
        }
