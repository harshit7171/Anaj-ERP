"""GST debit note add/modify with party/item/rate autofill."""

from __future__ import annotations

import json
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .documents import DocumentService
from .documents import PURCHASE_DOCUMENT_TYPES
from .documents import SALE_DOCUMENT_TYPES
from .errors import ValidationError

DOCUMENT_TYPE = "gst_debit_note"

SALE_SOURCE_TYPES = tuple(SALE_DOCUMENT_TYPES - {"gst_debit_note", "sale_memo", "outward"})
PURCHASE_SOURCE_TYPES = tuple(PURCHASE_DOCUMENT_TYPES)


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception as exc:
        raise ValidationError("Invalid number") from exc


def _money_paise(value: Any) -> int:
    return int((_dec(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _line_taxable(qty: Decimal, rate: Decimal, disc_amt: Decimal) -> Decimal:
    gross = (qty * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = gross - disc_amt
    return net if net > 0 else Decimal("0")


class GstDebitNoteEntryService:
    """Legacy GST debit note screen."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.documents = DocumentService(databases, company_id)

    def get_gst_debit_note_entry(
        self,
        financial_year_id: str,
        *,
        document_id: str = "",
        entry_date: str = "",
        party_id: str = "",
        d_note_no: str = "",
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
                note_sql = ""
                if d_note_no.strip():
                    note_sql = (
                        " AND (d.document_number = ? OR json_extract(d.header_metadata_json, '$.d_note_no') = ?)"
                    )
                    params.extend([d_note_no.strip(), d_note_no.strip()])
                row = connection.execute(
                    f"""
                    SELECT d.*, p.name AS party_name, p.gstin AS party_gstin
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type = ?
                      AND d.document_date = ?
                      AND d.party_id = ?
                    {note_sql}
                    ORDER BY d.updated_at DESC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
            if row is None:
                raise ValidationError("GST debit note not found")
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
        return payload

    def save_gst_debit_note_entry(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        document_id = str(payload.get("document_id") or "").strip()
        if document_id:
            self.delete_gst_debit_note_entry(financial_year_id, document_id)
        party_id = str(payload.get("party_id") or "").strip()
        if not party_id:
            raise ValidationError("Party A/c is required")
        entry_date = str(payload.get("entry_date") or "").strip()
        if not entry_date:
            raise ValidationError("Date is required")
        d_note_no = str(payload.get("d_note_no") or "").strip()
        document_number = str(payload.get("document_number") or "").strip() or d_note_no
        if not document_number:
            document_number = self.documents.next_document_number(
                financial_year_id,
                DOCUMENT_TYPE,
            )
        pur_sale = str(payload.get("pur_sale") or "S").strip().upper()
        inv_dir = "in" if pur_sale == "S" else "out"
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
            bags = _dec(raw.get("bags"))
            if qty <= 0 and bags > 0:
                qty = bags
            rate = _dec(raw.get("rate"))
            disc_pct = _dec(raw.get("disc_pct"))
            disc_amt = _dec(raw.get("disc_amt"))
            if disc_amt <= 0 and disc_pct > 0:
                disc_amt = (qty * rate * disc_pct / Decimal("100")).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
            if qty <= 0:
                continue
            taxable = _line_taxable(qty, rate, disc_amt)
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
                    "bags_scaled": int(bags.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                    "bag_scale": 0,
                    "packing_weight_scaled": 0,
                    "loose_quantity_scaled": 0,
                    "quantity_scaled": int(qty * 1000),
                    "quantity_scale": 3,
                    "rate_paise": _money_paise(rate),
                    "rate_unit": "quintal",
                    "metadata": {
                        **raw,
                        "taxable": str(taxable),
                        "amount": str(taxable),
                        "gst_amt": str(gst_amt),
                        "disc_amt": str(disc_amt),
                        "inventory_direction": inv_dir,
                    },
                }
            )
        if not document_lines:
            raise ValidationError("At least one valid line is required")
        header_meta = {k: v for k, v in payload.items() if k not in {"lines", "document_id"}}
        header_meta["d_note_no"] = d_note_no or document_number
        with self.databases.connect(self.database_path) as connection:
            main_account_id, party_account_id = self._resolve_accounts(connection, party_id, pur_sale)
        header = {
            "reference_number": str(payload.get("ref_no") or ""),
            "due_date": str(payload.get("due_date") or ""),
            "vehicle_number": str(payload.get("veh_no") or ""),
            "gr_number": str(payload.get("gr_no") or ""),
            "gr_date": str(payload.get("gr_date") or ""),
            "remarks": str(payload.get("remarks") or ""),
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
        return self.get_gst_debit_note_entry(financial_year_id, document_id=str(posted["document_id"]))

    def delete_gst_debit_note_entry(self, financial_year_id: str, document_id: str) -> dict[str, str]:
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
                raise ValidationError("GST debit note not found")
            voucher_id = str(row["posted_voucher_id"] or "")
            document_date = str(row["document_date"])
            document_number = str(row["document_number"])
        if voucher_id:
            AccountingService(self.databases, self.company_id).reverse_voucher(
                voucher_id,
                f"REV-{document_number}"[:24],
                document_date,
                "GST debit note modify or delete",
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
                SELECT party_id, name, gstin, city
                FROM party WHERE is_deleted = 0 AND name LIKE ?
                ORDER BY name COLLATE NOCASE LIMIT 40
                """,
                (pattern,),
            ).fetchall()
        return [dict(row) for row in rows]

    def lookup_line_accounts(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT account_id, name FROM account
                WHERE is_deleted = 0 AND account_type IN ('income', 'expense', 'party')
                  AND name LIKE ?
                ORDER BY name COLLATE NOCASE LIMIT 40
                """,
                (pattern,),
            ).fetchall()
        return [{"account_id": r["account_id"], "account_name": r["name"]} for r in rows]

    def lookup_line_items(
        self,
        financial_year_id: str,
        *,
        party_id: str,
        pur_sale: str = "S",
        query: str = "",
    ) -> list[dict[str, Any]]:
        if not party_id.strip():
            return []
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        doc_types = SALE_SOURCE_TYPES if str(pur_sale).upper() == "S" else PURCHASE_SOURCE_TYPES
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT co.commodity_id, co.name AS item_name, co.hsn_code
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                JOIN commodity co ON co.commodity_id = dl.commodity_id
                WHERE d.financial_year_id = ?
                  AND d.document_type IN ({", ".join("?" for _ in doc_types)})
                  AND d.party_id = ?
                  AND d.status = 'posted'
                  AND co.name LIKE ?
                ORDER BY co.name COLLATE NOCASE
                LIMIT 40
                """,
                (financial_year_id, *doc_types, party_id.strip(), pattern),
            ).fetchall()
        if not rows:
            rows = connection.execute(
                """
                SELECT commodity_id, name AS item_name, hsn_code
                FROM commodity
                WHERE is_deleted = 0 AND name LIKE ?
                ORDER BY name COLLATE NOCASE LIMIT 40
                """,
                (pattern,),
            ).fetchall()
        return [
            {
                "commodity_id": row["commodity_id"],
                "item_name": row["item_name"],
                "hsn_code": row["hsn_code"] or "",
            }
            for row in rows
        ]

    def lookup_line_rates(
        self,
        financial_year_id: str,
        *,
        party_id: str,
        commodity_id: str,
        pur_sale: str = "S",
    ) -> list[dict[str, Any]]:
        if not party_id.strip() or not commodity_id.strip():
            return []
        doc_types = SALE_SOURCE_TYPES if str(pur_sale).upper() == "S" else PURCHASE_SOURCE_TYPES
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT dl.rate_paise,
                       SUM(dl.quantity_scaled * 1.0 / POWER(10, dl.quantity_scale)) AS qty
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                WHERE d.financial_year_id = ?
                  AND d.document_type IN ({", ".join("?" for _ in doc_types)})
                  AND d.party_id = ?
                  AND dl.commodity_id = ?
                GROUP BY dl.rate_paise
                ORDER BY dl.rate_paise DESC
                LIMIT 20
                """,
                (financial_year_id, *doc_types, party_id.strip(), commodity_id.strip()),
            ).fetchall()
        return [
            {
                "rate": f"{int(row['rate_paise']) / 100:.2f}",
                "qty": f"{Decimal(str(row['qty'] or 0)):.2f}",
            }
            for row in rows
        ]

    def fill_from_source_document(
        self,
        financial_year_id: str,
        *,
        party_id: str,
        doc_no: str,
        pur_sale: str = "S",
    ) -> dict[str, Any]:
        """Copy lines from a posted sale/purchase document (Fill Data)."""
        if not party_id.strip() or not doc_no.strip():
            raise ValidationError("Party and Doc No. are required to fill data")
        doc_types = SALE_SOURCE_TYPES if str(pur_sale).upper() == "S" else PURCHASE_SOURCE_TYPES
        with self.databases.connect(self.database_path) as connection:
            doc = connection.execute(
                f"""
                SELECT document_id, document_date, reference_number
                FROM document
                WHERE financial_year_id = ?
                  AND document_type IN ({", ".join("?" for _ in doc_types)})
                  AND party_id = ?
                  AND (document_number = ? OR reference_number = ?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (financial_year_id, *doc_types, party_id.strip(), doc_no.strip(), doc_no.strip()),
            ).fetchone()
            if doc is None:
                raise ValidationError("Source document not found for this party")
            lines = connection.execute(
                """
                SELECT dl.*, co.name AS commodity_name
                FROM document_line dl
                JOIN commodity co ON co.commodity_id = dl.commodity_id
                WHERE dl.document_id = ?
                ORDER BY dl.line_number
                """,
                (str(doc["document_id"]),),
            ).fetchall()
        out_lines: list[dict[str, Any]] = []
        for line in lines:
            item = dict(line)
            meta = json.loads(str(item.get("line_metadata_json") or "{}"))
            item["metadata"] = meta
            out_lines.append(self._line_to_form(item))
        return {
            "doc_date": str(doc["document_date"]),
            "ref_no": str(doc["reference_number"] or doc_no),
            "lines": out_lines,
        }

    def next_entry_number(self, financial_year_id: str) -> str:
        return self.documents.next_document_number(financial_year_id, DOCUMENT_TYPE)

    @staticmethod
    def _resolve_accounts(connection: Any, party_id: str, pur_sale: str) -> tuple[str, str]:
        party = connection.execute(
            "SELECT account_id FROM party WHERE party_id = ? AND is_deleted = 0",
            (party_id,),
        ).fetchone()
        if party is None or not party["account_id"]:
            raise ValidationError("Party must have a linked ledger account")
        party_account_id = str(party["account_id"])
        if str(pur_sale).upper() == "P":
            main = connection.execute(
                """
                SELECT account_id FROM account
                WHERE is_deleted = 0 AND account_type = 'expense'
                  AND (name LIKE '%Purchase%' OR name LIKE '%GST%')
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
        else:
            main = connection.execute(
                """
                SELECT account_id FROM account
                WHERE is_deleted = 0 AND account_type = 'income'
                  AND (name LIKE '%Sale%' OR name LIKE '%Sales%')
                ORDER BY name COLLATE NOCASE LIMIT 1
                """
            ).fetchone()
            if main is None:
                main = connection.execute(
                    """
                    SELECT account_id FROM account
                    WHERE is_deleted = 0 AND account_type = 'income'
                    ORDER BY name COLLATE NOCASE LIMIT 1
                    """
                ).fetchone()
            if main is None:
                raise ValidationError("Create a Sales income account before posting")
        return str(main["account_id"]), party_account_id

    @staticmethod
    def _header_to_form(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        base = {
            "document_id": row["document_id"],
            "document_number": row["document_number"],
            "entry_date": row["document_date"],
            "party_id": row.get("party_id") or "",
            "party_name": row.get("party_name") or "",
            "d_note_no": meta.get("d_note_no") or row.get("document_number") or "",
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
        qty = Decimal(str(row.get("quantity_scaled") or 0)) / (Decimal(10) ** scale)
        rate = Decimal(int(row.get("rate_paise") or 0)) / Decimal(100)
        taxable = Decimal(str(meta.get("taxable") or meta.get("amount") or qty * rate))
        return {
            "line_account_id": meta.get("line_account_id") or "",
            "line_account_name": meta.get("line_account_name") or meta.get("line_ac") or "",
            "commodity_id": row.get("commodity_id"),
            "item_name": meta.get("item_name") or row.get("commodity_name") or "",
            "item_desc": meta.get("item_desc") or meta.get("item_name") or "",
            "bags": meta.get("bags") or str(row.get("bags_scaled") or ""),
            "qty": meta.get("qty") or f"{qty:.3f}",
            "rate": meta.get("rate") or f"{rate:.2f}",
            "disc_pct": meta.get("disc_pct") or "",
            "disc_amt": meta.get("disc_amt") or "",
            "amount": meta.get("amount") or f"{taxable:.2f}",
            "hsn_code": meta.get("hsn_code") or row.get("hsn_code") or "",
            "gst_diff": meta.get("gst_diff") or "",
            "cgst_pct": meta.get("cgst_pct") or "2.5",
            "sgst_pct": meta.get("sgst_pct") or "2.5",
            "igst_pct": meta.get("igst_pct") or "0",
            "gst_amt": meta.get("gst_amt") or "0.00",
        }
