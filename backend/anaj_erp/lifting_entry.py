"""Lifting entry (daily mandi) save, lookups, delete and challan printing."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .database import DatabaseManager
from .database import utc_now
from .documents import DocumentService
from .errors import ValidationError
from .lifting_challan_pdf import LiftingChallanPrinter

PURCHASE_DOCUMENT_TYPES = (
    "mandi_purchase",
    "kachi_purchase",
    "form_j",
    "purchase_invoice",
    "gst_purchase",
    "inward",
)


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception as exc:
        raise ValidationError("Invalid number") from exc


def _money_paise(value: Any) -> int:
    return int((_dec(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _line_amount(weight: Decimal, rate: Decimal) -> Decimal:
    return (weight * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LiftingEntryService:
    """Legacy-style lifting entry backed by posted lifting_entry documents."""

    DOCUMENT_TYPE = "lifting_entry"

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.documents = DocumentService(databases, company_id)

    def get_lifting_entry(
        self,
        financial_year_id: str,
        *,
        document_id: str = "",
        entry_date: str = "",
        challan_no: str = "",
        party_id: str = "",
    ) -> dict[str, Any]:
        """Load one lifting entry by id or by date + challan + party account."""
        with self.databases.connect(self.database_path) as connection:
            row = None
            clean_id = str(document_id or "").strip()
            if clean_id:
                row = connection.execute(
                    """
                    SELECT d.*, p.name AS party_name
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.document_id = ? AND d.document_type = ?
                    """,
                    (clean_id, self.DOCUMENT_TYPE),
                ).fetchone()
            else:
                if not entry_date.strip() or not challan_no.strip():
                    raise ValidationError("Date and challan number are required to find a lifting entry")
                params: list[Any] = [
                    financial_year_id,
                    self.DOCUMENT_TYPE,
                    entry_date.strip(),
                    challan_no.strip(),
                ]
                party_sql = ""
                if party_id.strip():
                    party_sql = " AND d.party_id = ?"
                    params.append(party_id.strip())
                row = connection.execute(
                    f"""
                    SELECT d.*, p.name AS party_name
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type = ?
                      AND d.document_date = ?
                      AND d.document_number = ?
                    {party_sql}
                    ORDER BY d.updated_at DESC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
            if row is None:
                raise ValidationError("Lifting entry not found")
            document_id = str(row["document_id"])
            lines = connection.execute(
                """
                SELECT dl.*, co.name AS commodity_name, sp.name AS source_party_name
                FROM document_line dl
                JOIN commodity co ON co.commodity_id = dl.commodity_id
                LEFT JOIN party sp ON sp.party_id = dl.source_party_id
                WHERE dl.document_id = ?
                ORDER BY dl.line_number
                """,
                (document_id,),
            ).fetchall()
        header_meta = json.loads(str(row["header_metadata_json"] or "{}"))
        payload = self._header_to_form(dict(row), header_meta)
        payload["lines"] = []
        for line in lines:
            row = dict(line)
            row["metadata"] = json.loads(str(row.get("line_metadata_json") or "{}"))
            payload["lines"].append(self._line_to_form(row))
        payload["expenses"] = list(header_meta.get("expenses") or [])
        payload["lifted_summary"] = list(header_meta.get("lifted_summary") or [])
        return payload

    def save_lifting_entry(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or replace a lifting entry document."""
        document_id = str(payload.get("document_id") or "").strip()
        if document_id:
            self.delete_lifting_entry(financial_year_id, document_id)
        party_id = str(payload.get("party_id") or "").strip()
        if not party_id:
            raise ValidationError("Party A/c is required")
        entry_date = str(payload.get("entry_date") or "").strip()
        challan_no = str(payload.get("challan_no") or "").strip()
        if not entry_date or not challan_no:
            raise ValidationError("Date and challan number are required")
        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ValidationError("At least one lifting line is required")
        document_lines: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_lines, start=1):
            if not isinstance(raw, dict):
                continue
            commodity_id = str(raw.get("commodity_id") or "").strip()
            if not commodity_id:
                continue
            qty = _dec(raw.get("qty"))
            weight = _dec(raw.get("weight"))
            rate = _dec(raw.get("rate"))
            if weight <= 0 and qty <= 0:
                continue
            amount = _line_amount(weight, rate) if weight > 0 else _line_amount(qty, rate)
            document_lines.append(
                {
                    "commodity_id": commodity_id,
                    "description": str(raw.get("item_name") or "Commodity"),
                    "source_party_id": raw.get("line_party_id") or None,
                    "source_reference_number": str(raw.get("reference") or ""),
                    "bags_scaled": int(qty.quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                    "bag_scale": 0,
                    "packing_weight_scaled": 0,
                    "loose_quantity_scaled": 0,
                    "quantity_scaled": int((weight if weight > 0 else qty) * 1000),
                    "quantity_scale": 3,
                    "rate_paise": _money_paise(rate),
                    "rate_unit": "quintal",
                    "metadata": {
                        "item_name": raw.get("item_name"),
                        "party_name": raw.get("party_name"),
                        "remarks": raw.get("remarks"),
                        "unit": raw.get("unit"),
                        "ref_code": raw.get("ref_code"),
                        "reference": raw.get("reference"),
                        "qty": str(qty),
                        "weight": str(weight),
                        "amount": str(amount),
                    },
                }
            )
        if not document_lines:
            raise ValidationError("At least one valid lifting line is required")
        totals = payload.get("totals") or {}
        header_meta = {
            "user_name": payload.get("user_name"),
            "dispatch_from": payload.get("dispatch_from"),
            "prefix": payload.get("prefix"),
            "po_no": payload.get("po_no"),
            "po_date": payload.get("po_date"),
            "kanda_wt": payload.get("kanda_wt"),
            "actual_wt": payload.get("actual_wt"),
            "transport": payload.get("transport"),
            "policy_no": payload.get("policy_no"),
            "expenses": payload.get("expenses") or [],
            "lifted_summary": payload.get("lifted_summary") or [],
            "totals": totals,
        }
        header = {
            "vehicle_number": str(payload.get("vehicle_no") or ""),
            "driver_name": str(payload.get("driver_name") or ""),
            "gr_number": str(payload.get("gr_no") or ""),
            "gr_date": str(payload.get("gr_date") or ""),
            "from_place": str(payload.get("dispatch_from") or ""),
            "remarks": str(payload.get("remarks") or ""),
            "po_number": str(payload.get("po_no") or ""),
            "insurance_number": str(payload.get("policy_no") or ""),
            "metadata": header_meta,
        }
        posted = self.documents.post(
            financial_year_id=financial_year_id,
            document_type=self.DOCUMENT_TYPE,
            document_number=challan_no,
            document_date=entry_date,
            party_id=party_id,
            lines=document_lines,
            header=header,
        )
        return self.get_lifting_entry(financial_year_id, document_id=str(posted["document_id"]))

    def delete_lifting_entry(self, financial_year_id: str, document_id: str) -> dict[str, str]:
        """Remove a lifting entry and its inventory movements."""
        clean = str(document_id or "").strip()
        if not clean:
            raise ValidationError("Document id is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT document_id FROM document
                WHERE document_id = ? AND financial_year_id = ? AND document_type = ?
                """,
                (clean, financial_year_id, self.DOCUMENT_TYPE),
            ).fetchone()
            if row is None:
                raise ValidationError("Lifting entry not found")
            connection.execute(
                "DELETE FROM inventory_movement WHERE document_id = ?",
                (clean,),
            )
            connection.execute("DELETE FROM document_charge WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document_line WHERE document_id = ?", (clean,))
            connection.execute("DELETE FROM document WHERE document_id = ?", (clean,))
        return {"document_id": clean}

    def lookup_line_parties(
        self,
        financial_year_id: str,
        *,
        header_party_id: str,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Party names with available purchase qty for lifting (line party picker)."""
        if not header_party_id.strip():
            return []
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                WITH purchase AS (
                    SELECT
                        dl.source_party_id AS line_party_id,
                        sp.name AS party_name,
                        sp.city,
                        dl.commodity_id,
                        SUM(dl.quantity_scaled * 1.0 / POWER(10, dl.quantity_scale)) AS purchased_qty
                    FROM document_line dl
                    JOIN document d ON d.document_id = dl.document_id
                    LEFT JOIN party sp ON sp.party_id = dl.source_party_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type IN ({purchase_types})
                      AND d.status = 'posted'
                      AND dl.source_party_id IS NOT NULL
                    GROUP BY dl.source_party_id, sp.name, sp.city, dl.commodity_id
                ),
                lifted AS (
                    SELECT
                        dl.source_party_id AS line_party_id,
                        dl.commodity_id,
                        SUM(dl.quantity_scaled * 1.0 / POWER(10, dl.quantity_scale)) AS lifted_qty
                    FROM document_line dl
                    JOIN document d ON d.document_id = dl.document_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type = ?
                      AND d.status = 'posted'
                    GROUP BY dl.source_party_id, dl.commodity_id
                )
                SELECT
                    p.line_party_id,
                    p.party_name,
                    p.city,
                    SUM(p.purchased_qty - COALESCE(l.lifted_qty, 0)) AS available_qty
                FROM purchase p
                LEFT JOIN lifted l
                  ON l.line_party_id = p.line_party_id
                 AND l.commodity_id = p.commodity_id
                WHERE p.party_name LIKE ?
                GROUP BY p.line_party_id, p.party_name, p.city
                HAVING available_qty > 0
                ORDER BY p.party_name COLLATE NOCASE
                LIMIT 40
                """.format(
                    purchase_types=", ".join("?" for _ in PURCHASE_DOCUMENT_TYPES),
                ),
                (
                    financial_year_id,
                    *PURCHASE_DOCUMENT_TYPES,
                    financial_year_id,
                    self.DOCUMENT_TYPE,
                    pattern,
                ),
            ).fetchall()
        return [
            {
                "party_id": row["line_party_id"],
                "party_name": row["party_name"],
                "city": row["city"],
                "qty": f"{Decimal(str(row['available_qty'] or 0)):.2f}",
            }
            for row in rows
        ]

    def lookup_line_items(
        self,
        financial_year_id: str,
        *,
        line_party_id: str,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Item names with remaining qty for a line party."""
        if not line_party_id.strip():
            return []
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                WITH purchase AS (
                    SELECT
                        dl.commodity_id,
                        co.name AS item_name,
                        SUM(dl.quantity_scaled * 1.0 / POWER(10, dl.quantity_scale)) AS purchased_qty
                    FROM document_line dl
                    JOIN document d ON d.document_id = dl.document_id
                    JOIN commodity co ON co.commodity_id = dl.commodity_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type IN ({purchase_types})
                      AND d.status = 'posted'
                      AND dl.source_party_id = ?
                    GROUP BY dl.commodity_id, co.name
                ),
                lifted AS (
                    SELECT
                        dl.commodity_id,
                        SUM(dl.quantity_scaled * 1.0 / POWER(10, dl.quantity_scale)) AS lifted_qty
                    FROM document_line dl
                    JOIN document d ON d.document_id = dl.document_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type = ?
                      AND d.status = 'posted'
                      AND dl.source_party_id = ?
                    GROUP BY dl.commodity_id
                )
                SELECT
                    p.commodity_id,
                    p.item_name,
                    (p.purchased_qty - COALESCE(l.lifted_qty, 0)) AS available_qty
                FROM purchase p
                LEFT JOIN lifted l ON l.commodity_id = p.commodity_id
                WHERE p.item_name LIKE ?
                  AND (p.purchased_qty - COALESCE(l.lifted_qty, 0)) > 0
                ORDER BY p.item_name COLLATE NOCASE
                LIMIT 30
                """.format(
                    purchase_types=", ".join("?" for _ in PURCHASE_DOCUMENT_TYPES),
                ),
                (
                    financial_year_id,
                    *PURCHASE_DOCUMENT_TYPES,
                    line_party_id,
                    financial_year_id,
                    self.DOCUMENT_TYPE,
                    line_party_id,
                    pattern,
                ),
            ).fetchall()
        return [
            {
                "commodity_id": row["commodity_id"],
                "item_name": row["item_name"],
                "qty": f"{Decimal(str(row['available_qty'] or 0)):.2f}",
            }
            for row in rows
        ]

    def lookup_line_rates(
        self,
        financial_year_id: str,
        *,
        line_party_id: str,
        commodity_id: str,
        ref_code: str = "",
    ) -> list[dict[str, Any]]:
        """Rate and qty pairs from purchase history."""
        if not line_party_id.strip() or not commodity_id.strip():
            return []
        with self.databases.connect(self.database_path) as connection:
            params: list[Any] = [
                financial_year_id,
                *PURCHASE_DOCUMENT_TYPES,
                line_party_id,
                commodity_id,
            ]
            ref_filter = ""
            if ref_code.strip():
                ref_filter = " AND json_extract(dl.line_metadata_json, '$.ref_code') = ?"
                params.append(ref_code.strip())
            rows = connection.execute(
                f"""
                SELECT
                    dl.rate_paise,
                    SUM(dl.quantity_scaled * 1.0 / POWER(10, dl.quantity_scale)) AS qty
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                WHERE d.financial_year_id = ?
                  AND d.document_type IN ({", ".join("?" for _ in PURCHASE_DOCUMENT_TYPES)})
                  AND dl.source_party_id = ?
                  AND dl.commodity_id = ?
                {ref_filter}
                GROUP BY dl.rate_paise
                ORDER BY dl.rate_paise DESC
                LIMIT 20
                """,
                params,
            ).fetchall()
        return [
            {
                "rate": f"{int(row['rate_paise']) / 100:.2f}",
                "qty": f"{Decimal(str(row['qty'] or 0)):.2f}",
            }
            for row in rows
        ]

    def lookup_purchase_references(
        self,
        financial_year_id: str,
        *,
        line_party_id: str,
        commodity_id: str,
        ref_code: str,
    ) -> list[dict[str, Any]]:
        """Bill reference rows for ref code picker."""
        if not line_party_id.strip() or not commodity_id.strip() or not ref_code.strip():
            return []
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    dl.source_reference_number,
                    d.document_number AS bill_no,
                    d.document_date AS bill_date,
                    dl.quantity_scaled,
                    dl.quantity_scale,
                    dl.rate_paise
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                WHERE d.financial_year_id = ?
                  AND d.document_type IN ({purchase_types})
                  AND dl.source_party_id = ?
                  AND dl.commodity_id = ?
                  AND (
                    json_extract(dl.line_metadata_json, '$.ref_code') = ?
                    OR dl.source_reference_number LIKE ?
                  )
                ORDER BY d.document_date DESC, d.document_number DESC
                LIMIT 30
                """.format(
                    purchase_types=", ".join("?" for _ in PURCHASE_DOCUMENT_TYPES),
                ),
                (
                    financial_year_id,
                    *PURCHASE_DOCUMENT_TYPES,
                    line_party_id,
                    commodity_id,
                    ref_code,
                    f"{ref_code}%",
                ),
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            qty = Decimal(str(row["quantity_scaled"])) / (
                Decimal(10) ** int(row["quantity_scale"])
            )
            bill_no = str(row["bill_no"] or "")
            bill_date = str(row["bill_date"] or "")
            reference = str(row["source_reference_number"] or "")
            if not reference and bill_no:
                reference = f"{bill_no}-{bill_date}"
            results.append(
                {
                    "ref_code": ref_code,
                    "bill_no": bill_no,
                    "bill_date": bill_date,
                    "reference": reference,
                    "qty": f"{qty:.2f}",
                    "rate": f"{int(row['rate_paise']) / 100:.2f}",
                }
            )
        return results

    def lifted_qty_by_item(
        self,
        financial_year_id: str,
        *,
        party_id: str,
        dispatch_from: str = "",
    ) -> list[dict[str, Any]]:
        """Top-right Item/Crop lifted qty panel."""
        if not party_id.strip():
            return []
        with self.databases.connect(self.database_path) as connection:
            params: list[Any] = [financial_year_id, self.DOCUMENT_TYPE, party_id]
            place_filter = ""
            if dispatch_from.strip():
                place_filter = " AND d.from_place = ?"
                params.append(dispatch_from.strip())
            rows = connection.execute(
                f"""
                SELECT co.name AS item_name,
                       SUM(dl.quantity_scaled * 1.0 / POWER(10, dl.quantity_scale)) AS lifted_qty
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                JOIN commodity co ON co.commodity_id = dl.commodity_id
                WHERE d.financial_year_id = ?
                  AND d.document_type = ?
                  AND d.party_id = ?
                  {place_filter}
                GROUP BY co.name
                ORDER BY co.name COLLATE NOCASE
                """,
                params,
            ).fetchall()
        return [
            {
                "item_name": row["item_name"],
                "lifted_qty": f"{Decimal(str(row['lifted_qty'] or 0)):.2f}",
            }
            for row in rows
        ]

    def print_lifting_challans(
        self,
        financial_year_id: str,
        *,
        party_name: str,
        from_challan: int,
        to_challan: int,
        save_pdf: bool = True,
        copy_label: str = "original",
    ) -> dict[str, Any]:
        """Generate delivery challan PDFs for a challan number range."""
        if from_challan <= 0 or to_challan < from_challan:
            raise ValidationError("Invalid challan range")
        created: list[str] = []
        printer = LiftingChallanPrinter(self.documents)
        output_dir = self.database_path.parent / "lifting_prints"
        output_dir.mkdir(parents=True, exist_ok=True)
        with self.databases.connect(self.database_path) as connection:
            for challan in range(from_challan, to_challan + 1):
                row = connection.execute(
                    """
                    SELECT d.document_id
                    FROM document d
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.financial_year_id = ?
                      AND d.document_type = ?
                      AND d.document_number = ?
                      AND (? = '' OR p.name LIKE ?)
                    ORDER BY d.document_date DESC
                    LIMIT 1
                    """,
                    (
                        financial_year_id,
                        self.DOCUMENT_TYPE,
                        str(challan),
                        party_name.strip(),
                        f"%{party_name.strip()}%",
                    ),
                ).fetchone()
                if row is None:
                    continue
                path = output_dir / f"lifting_{challan}_{uuid.uuid4().hex[:8]}.pdf"
                printer.create_pdf(str(row["document_id"]), path, copy_label=copy_label)
                created.append(str(path))
        return {"pdf_paths": created, "count": len(created)}

    @staticmethod
    def _header_to_form(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_id": row["document_id"],
            "entry_date": row["document_date"],
            "challan_no": row["document_number"],
            "party_id": row["party_id"],
            "party_name": row.get("party_name") or "",
            "user_name": meta.get("user_name") or "USER",
            "dispatch_from": meta.get("dispatch_from") or row.get("from_place") or "",
            "prefix": meta.get("prefix") or "",
            "vehicle_no": row.get("vehicle_number") or "",
            "gr_no": row.get("gr_number") or "",
            "gr_date": row.get("gr_date") or "",
            "transport": meta.get("transport") or "",
            "driver_name": row.get("driver_name") or "",
            "remarks": row.get("remarks") or "",
            "policy_no": meta.get("policy_no") or row.get("insurance_number") or "",
            "po_no": meta.get("po_no") or row.get("po_number") or "",
            "po_date": meta.get("po_date") or "",
            "kanda_wt": meta.get("kanda_wt") or "",
            "actual_wt": meta.get("actual_wt") or "",
            "totals": meta.get("totals") or {},
        }

    @staticmethod
    def _line_to_form(row: dict[str, Any]) -> dict[str, Any]:
        meta = row.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        qty_scale = int(row.get("quantity_scale") or 3)
        weight = Decimal(str(row.get("quantity_scaled") or 0)) / (Decimal(10) ** qty_scale)
        return {
            "line_number": row.get("line_number"),
            "commodity_id": row.get("commodity_id"),
            "item_name": meta.get("item_name") or row.get("commodity_name") or "",
            "party_name": meta.get("party_name") or row.get("source_party_name") or "",
            "line_party_id": row.get("source_party_id"),
            "remarks": meta.get("remarks") or "",
            "unit": meta.get("unit") or "Qtls",
            "ref_code": meta.get("ref_code") or "",
            "reference": meta.get("reference") or row.get("source_reference_number") or "",
            "qty": meta.get("qty") or str(row.get("bags_scaled") or ""),
            "weight": meta.get("weight") or f"{weight:.3f}",
            "rate": f"{int(row.get('rate_paise') or 0) / 100:.2f}",
            "amount": meta.get("amount")
            or f"{_line_amount(weight, Decimal(int(row.get('rate_paise') or 0)) / 100):.2f}",
        }
