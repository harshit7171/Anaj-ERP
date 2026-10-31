"""Kachi purchase add/modify backed by kachi_purchase documents."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .documents import DocumentService
from .errors import ValidationError

DOCUMENT_TYPE = "kachi_purchase"


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception as exc:
        raise ValidationError("Invalid number") from exc


def _money_paise(value: Any) -> int:
    return int((_dec(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _line_amount(weight: Decimal, rate: Decimal) -> Decimal:
    return (weight * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class KachiPurchaseService:
    """Legacy kachi purchase screen (seller lines, PO, mandi, buyer)."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.documents = DocumentService(databases, company_id)

    def get_kachi_purchase(
        self,
        financial_year_id: str,
        *,
        document_id: str = "",
        entry_date: str = "",
        po_no: str = "",
        buyer_party_id: str = "",
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            row = None
            clean_id = str(document_id or "").strip()
            if clean_id:
                row = connection.execute(
                    """
                    SELECT d.*, p.name AS buyer_name
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.document_id = ? AND d.document_type = ?
                    """,
                    (clean_id, DOCUMENT_TYPE),
                ).fetchone()
            else:
                if not entry_date.strip() or not po_no.strip():
                    raise ValidationError("Date and P.O. No. are required to find a kachi bill")
                params: list[Any] = [
                    financial_year_id,
                    DOCUMENT_TYPE,
                    entry_date.strip(),
                    po_no.strip(),
                ]
                buyer_sql = ""
                if buyer_party_id.strip():
                    buyer_sql = " AND d.party_id = ?"
                    params.append(buyer_party_id.strip())
                row = connection.execute(
                    f"""
                    SELECT d.*, p.name AS buyer_name
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type = ?
                      AND d.document_date = ?
                      AND d.po_number = ?
                    {buyer_sql}
                    ORDER BY d.updated_at DESC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
            if row is None:
                raise ValidationError("Kachi purchase not found")
            document_id = str(row["document_id"])
            lines = connection.execute(
                """
                SELECT dl.*, co.name AS commodity_name, sp.name AS seller_name
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
        return payload

    def save_kachi_purchase(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        document_id = str(payload.get("document_id") or "").strip()
        if document_id:
            self.delete_kachi_purchase(financial_year_id, document_id)
        buyer_party_id = str(payload.get("buyer_party_id") or "").strip()
        if not buyer_party_id:
            raise ValidationError("Buyer is required")
        entry_date = str(payload.get("entry_date") or "").strip()
        po_no = str(payload.get("po_no") or "").strip()
        if not entry_date or not po_no:
            raise ValidationError("Date and P.O. No. are required")
        mandi = str(payload.get("mandi") or "").strip()
        lock_hours = str(payload.get("lock_hours") or "24")
        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ValidationError("At least one purchase line is required")
        document_lines: list[dict[str, Any]] = []
        for raw in raw_lines:
            if not isinstance(raw, dict):
                continue
            commodity_id = str(raw.get("commodity_id") or "").strip()
            seller_party_id = str(raw.get("seller_party_id") or "").strip()
            if not commodity_id or not seller_party_id:
                continue
            bags = _dec(raw.get("bags"))
            bharti = _dec(raw.get("bharti"))
            weight = _dec(raw.get("weight"))
            if weight <= 0 and bharti > 0:
                weight = bharti
            rate = _dec(raw.get("rate"))
            if weight <= 0:
                continue
            amount = _line_amount(weight, rate)
            slip_no = str(raw.get("slip_no") or "")
            bill_no = str(raw.get("bill_no") or "")
            bill_date = str(raw.get("bill_date") or "")
            ref = bill_no or slip_no
            if bill_no and bill_date:
                ref = f"{bill_no}-{bill_date}"
            document_lines.append(
                {
                    "commodity_id": commodity_id,
                    "description": str(raw.get("item_name") or "Commodity"),
                    "source_party_id": seller_party_id,
                    "source_reference_number": ref,
                    "bags_scaled": int(bags.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                    "bag_scale": 0,
                    "packing_weight_scaled": int(bharti * 1000) if bharti else 0,
                    "loose_quantity_scaled": 0,
                    "quantity_scaled": int(weight * 1000),
                    "quantity_scale": 3,
                    "rate_paise": _money_paise(rate),
                    "rate_unit": "quintal",
                    "metadata": {
                        "seller_name": raw.get("seller_name"),
                        "slip_no": slip_no,
                        "bill_no": bill_no,
                        "bill_date": bill_date,
                        "item_name": raw.get("item_name"),
                        "bharti": str(bharti),
                        "bags": str(bags),
                        "weight": str(weight),
                        "rate": str(rate),
                        "amount": str(amount),
                    },
                }
            )
        if not document_lines:
            raise ValidationError("At least one valid line is required")
        totals = payload.get("totals") or {}
        header_meta = {
            "user_name": payload.get("user_name") or "USER",
            "mandi": mandi,
            "lock_hours": lock_hours,
            "po_no": po_no,
            "totals": totals,
            "final_status": payload.get("final_status") or "Open",
        }
        document_number = str(payload.get("document_number") or po_no)
        with self.databases.connect(self.database_path) as connection:
            main_account_id, party_account_id = self._resolve_accounts(
                connection,
                buyer_party_id,
            )
        header = {
            "from_place": mandi,
            "po_number": po_no,
            "metadata": header_meta,
        }
        posted = self.documents.post(
            financial_year_id=financial_year_id,
            document_type=DOCUMENT_TYPE,
            document_number=document_number,
            document_date=entry_date,
            party_id=buyer_party_id,
            main_account_id=main_account_id,
            party_account_id=party_account_id,
            lines=document_lines,
            header=header,
        )
        return self.get_kachi_purchase(financial_year_id, document_id=str(posted["document_id"]))

    def delete_kachi_purchase(self, financial_year_id: str, document_id: str) -> dict[str, str]:
        clean = str(document_id or "").strip()
        if not clean:
            raise ValidationError("Document id is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT document_id, posted_voucher_id, document_date, document_number
                FROM document
                WHERE document_id = ? AND financial_year_id = ? AND document_type = ?
                """,
                (clean, financial_year_id, DOCUMENT_TYPE),
            ).fetchone()
            if row is None:
                raise ValidationError("Kachi purchase not found")
            voucher_id = str(row["posted_voucher_id"] or "")
            document_date = str(row["document_date"])
            document_number = str(row["document_number"])
        if voucher_id:
            AccountingService(self.databases, self.company_id).reverse_voucher(
                voucher_id,
                f"REV-{document_number}"[:24],
                document_date,
                "Kachi purchase modify or delete",
            )
        with self.databases.connect(self.database_path) as connection:
            connection.execute("DELETE FROM inventory_movement WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document_charge WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document_line WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document WHERE document_id = ?", (clean,))
        return {"document_id": clean}

    def lookup_sellers(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT party_id, name, city, phone
                FROM party
                WHERE is_deleted = 0 AND name LIKE ?
                ORDER BY name COLLATE NOCASE
                LIMIT 40
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
                WHERE is_deleted = 0
                  AND (name LIKE ? OR variety LIKE ?)
                ORDER BY name COLLATE NOCASE
                LIMIT 40
                """,
                (pattern, pattern),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            name = str(row["name"] or "")
            variety = str(row["variety"] or "").strip()
            item_name = f"{name} {variety}".strip() if variety else name
            result.append({"commodity_id": row["commodity_id"], "item_name": item_name})
        return result

    def lookup_rates(
        self,
        financial_year_id: str,
        *,
        seller_party_id: str,
        commodity_id: str,
    ) -> list[dict[str, Any]]:
        if not seller_party_id.strip() or not commodity_id.strip():
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
                LIMIT 15
                """,
                (financial_year_id, DOCUMENT_TYPE, seller_party_id, commodity_id),
            ).fetchall()
        return [
            {
                "rate": f"{int(row['rate_paise']) / 100:.2f}",
                "weight": f"{Decimal(str(row['weight'] or 0)):.3f}",
            }
            for row in rows
        ]

    def suggest_po_no(self, financial_year_id: str, entry_date: str) -> str:
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT MAX(CAST(po_number AS INTEGER)) AS max_po
                FROM document
                WHERE financial_year_id = ?
                  AND document_type = ?
                  AND document_date = ?
                  AND po_number GLOB '[0-9]*'
                """,
                (financial_year_id, DOCUMENT_TYPE, entry_date),
            ).fetchone()
        current = int(row["max_po"] or 0) if row else 0
        return str(current + 1)

    @staticmethod
    def _resolve_accounts(connection: Any, buyer_party_id: str) -> tuple[str, str]:
        buyer = connection.execute(
            "SELECT account_id FROM party WHERE party_id = ? AND is_deleted = 0",
            (buyer_party_id,),
        ).fetchone()
        if buyer is None or not buyer["account_id"]:
            raise ValidationError("Buyer party must have a linked ledger account")
        party_account_id = str(buyer["account_id"])
        main = connection.execute(
            """
            SELECT account_id FROM account
            WHERE is_deleted = 0
              AND account_type IN ('expense', 'purchase')
              AND (name LIKE '%Kachi%' OR name LIKE '%Purchase%')
            ORDER BY name COLLATE NOCASE
            LIMIT 1
            """
        ).fetchone()
        if main is None:
            main = connection.execute(
                """
                SELECT account_id FROM account
                WHERE is_deleted = 0 AND account_type = 'expense'
                ORDER BY name COLLATE NOCASE
                LIMIT 1
                """
            ).fetchone()
        if main is None:
            raise ValidationError("Create a Purchase expense account before posting kachi purchase")
        return str(main["account_id"]), party_account_id

    @staticmethod
    def _header_to_form(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_id": row["document_id"],
            "document_number": row["document_number"],
            "entry_date": row["document_date"],
            "po_no": meta.get("po_no") or row.get("po_number") or "",
            "mandi": meta.get("mandi") or row.get("from_place") or "",
            "lock_hours": meta.get("lock_hours") or "24",
            "buyer_party_id": row.get("party_id") or "",
            "buyer_name": row.get("buyer_name") or "",
            "user_name": meta.get("user_name") or "USER",
            "final_status": meta.get("final_status") or "Open",
            "totals": meta.get("totals") or {},
        }

    @staticmethod
    def _line_to_form(row: dict[str, Any]) -> dict[str, Any]:
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        scale = int(row.get("quantity_scale") or 3)
        weight = Decimal(str(row.get("quantity_scaled") or 0)) / (Decimal(10) ** scale)
        return {
            "commodity_id": row.get("commodity_id"),
            "seller_party_id": row.get("source_party_id"),
            "seller_name": meta.get("seller_name") or row.get("seller_name") or "",
            "slip_no": meta.get("slip_no") or "",
            "bill_no": meta.get("bill_no") or "",
            "bill_date": meta.get("bill_date") or "",
            "item_name": meta.get("item_name") or row.get("commodity_name") or "",
            "bharti": meta.get("bharti") or "",
            "bags": meta.get("bags") or str(row.get("bags_scaled") or ""),
            "weight": meta.get("weight") or f"{weight:.3f}",
            "rate": meta.get("rate") or f"{int(row.get('rate_paise') or 0) / 100:.2f}",
            "amount": meta.get("amount")
            or f"{_line_amount(weight, Decimal(int(row.get('rate_paise') or 0)) / 100):.2f}",
        }
