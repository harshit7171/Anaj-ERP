"""TDS Challan Entry Add / Modify — link pending TDS charges to a challan."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .database import DatabaseManager
from .database import utc_now
from .errors import ValidationError

MINOR_HEADS = ("200", "400", "800")


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception as exc:
        raise ValidationError("Invalid number") from exc


def _money_paise(value: Any) -> int:
    return int((_dec(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class TdsChallanEntryService:
    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)

    def list_deductee_codes(self) -> list[str]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT json_extract(COALESCE(a.metadata_json, '{}'), '$.tds_deductee_code') AS code
                FROM party p
                JOIN account a ON a.account_id = p.account_id
                WHERE p.is_deleted = 0
                  AND code IS NOT NULL AND trim(code) != ''
                ORDER BY code COLLATE NOCASE
                """
            ).fetchall()
        codes = ["All", *[str(row["code"]) for row in rows if row["code"]]]
        return codes

    def next_challan_id(self, financial_year_id: str) -> str:
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT challan_display_id FROM tds_challan
                WHERE financial_year_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (financial_year_id,),
            ).fetchone()
        if row is None:
            return "1"
        text = str(row["challan_display_id"])
        digits = "".join(ch for ch in text if ch.isdigit())
        return str(int(digits) + 1 if digits else 1)

    def list_pending_lines(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        deductee_code: str = "All",
        *,
        challan_id: str = "",
    ) -> list[dict[str, Any]]:
        params: list[Any] = [financial_year_id, date_from, date_to]
        deductee_sql = ""
        if deductee_code.strip() and deductee_code.strip().lower() != "all":
            deductee_sql = (
                " AND json_extract(COALESCE(pa.metadata_json, '{}'), '$.tds_deductee_code') = ?"
            )
            params.append(deductee_code.strip())
        challan_sql = " AND (dc.tds_challan_id IS NULL OR dc.tds_challan_id = '')"
        if challan_id.strip():
            challan_sql = " AND (dc.tds_challan_id IS NULL OR dc.tds_challan_id = '' OR dc.tds_challan_id = ?)"
            params.append(challan_id.strip())
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    dc.document_charge_id,
                    d.document_date,
                    p.name AS party_name,
                    dc.label AS particulars,
                    d.subtotal_paise AS amount_paise,
                    dc.final_amount_paise AS tds_paise,
                    dc.challan_no,
                    dc.tds_challan_id
                FROM document_charge dc
                JOIN document d ON d.document_id = dc.document_id
                LEFT JOIN party p ON p.party_id = d.party_id
                LEFT JOIN account pa ON pa.account_id = p.account_id
                WHERE d.financial_year_id = ?
                  AND d.status = 'posted'
                  AND d.document_date BETWEEN ? AND ?
                  AND dc.code LIKE 'TDS%'
                  {deductee_sql}
                  {challan_sql}
                ORDER BY d.document_date, p.name, dc.line_number
                """,
                params,
            ).fetchall()
        result: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            item = dict(row)
            item["serial_no"] = index
            item["amount"] = f"{int(item['amount_paise']) / 100:.2f}"
            item["tds"] = f"{int(item['tds_paise']) / 100:.2f}"
            item["selected"] = bool(
                challan_id.strip() and str(item.get("tds_challan_id") or "") == challan_id.strip()
            )
            result.append(item)
        return result

    def get_challan_entry(
        self,
        financial_year_id: str,
        *,
        challan_id: str = "",
        challan_display_id: str = "",
        challan_date: str = "",
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            row = None
            if challan_id.strip():
                row = connection.execute(
                    "SELECT * FROM tds_challan WHERE tds_challan_id = ? AND financial_year_id = ?",
                    (challan_id.strip(), financial_year_id),
                ).fetchone()
            elif challan_display_id.strip() and challan_date.strip():
                row = connection.execute(
                    """
                    SELECT * FROM tds_challan
                    WHERE financial_year_id = ? AND challan_date = ? AND challan_display_id = ?
                    LIMIT 1
                    """,
                    (financial_year_id, challan_date.strip(), challan_display_id.strip()),
                ).fetchone()
            if row is None:
                raise ValidationError("TDS challan not found")
        cid = str(row["tds_challan_id"])
        lines = self.list_pending_lines(
            financial_year_id,
            str(row["filter_date_from"]),
            str(row["filter_date_to"]),
            str(row["deductee_code"] or "All"),
            challan_id=cid,
        )
        for line in lines:
            line["selected"] = str(line.get("tds_challan_id") or "") == cid
        return self._row_to_form(dict(row), lines)

    def save_challan_entry(self, financial_year_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        challan_id = str(payload.get("challan_id") or "").strip()
        if not challan_id:
            challan_id = str(uuid.uuid4())
        display_id = str(payload.get("challan_display_id") or "").strip()
        if not display_id:
            display_id = self.next_challan_id(financial_year_id)
        challan_date = str(payload.get("challan_date") or "").strip()
        if not challan_date:
            raise ValidationError("Challan date is required")
        challan_no = str(payload.get("challan_no") or "").strip()
        selected = payload.get("selected_charge_ids") or []
        if not isinstance(selected, list):
            selected = []
        charge_ids = [str(item).strip() for item in selected if str(item).strip()]
        if not charge_ids:
            raise ValidationError("Select at least one TDS line")
        tds_total = 0
        with self.databases.connect(self.database_path) as connection:
            placeholders = ",".join("?" for _ in charge_ids)
            rows = connection.execute(
                f"""
                SELECT document_charge_id, final_amount_paise, tds_challan_id
                FROM document_charge
                WHERE document_charge_id IN ({placeholders})
                """,
                tuple(charge_ids),
            ).fetchall()
            if len(rows) != len(charge_ids):
                raise ValidationError("One or more TDS lines are invalid")
            for row in rows:
                owner = str(row["tds_challan_id"] or "")
                if owner and owner != challan_id:
                    raise ValidationError("A selected line is already linked to another challan")
                tds_total += int(row["final_amount_paise"])
        total_amt = _money_paise(payload.get("total_amt")) or tds_total
        timestamp = utc_now()
        filter_from = str(payload.get("filter_date_from") or challan_date)
        filter_to = str(payload.get("filter_date_to") or challan_date)
        deductee = str(payload.get("deductee_code") or "All")
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO tds_challan(
                    tds_challan_id, financial_year_id, challan_display_id, challan_date,
                    nature, filter_date_from, filter_date_to, deductee_code,
                    challan_no, minor_head, bsr_code, chq_no,
                    tds_total_paise, total_amt_paise, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tds_challan_id) DO UPDATE SET
                    challan_display_id = excluded.challan_display_id,
                    challan_date = excluded.challan_date,
                    nature = excluded.nature,
                    filter_date_from = excluded.filter_date_from,
                    filter_date_to = excluded.filter_date_to,
                    deductee_code = excluded.deductee_code,
                    challan_no = excluded.challan_no,
                    minor_head = excluded.minor_head,
                    bsr_code = excluded.bsr_code,
                    chq_no = excluded.chq_no,
                    tds_total_paise = excluded.tds_total_paise,
                    total_amt_paise = excluded.total_amt_paise,
                    updated_at = excluded.updated_at
                """,
                (
                    challan_id,
                    financial_year_id,
                    display_id,
                    challan_date,
                    str(payload.get("nature") or ""),
                    filter_from,
                    filter_to,
                    deductee,
                    challan_no,
                    str(payload.get("minor_head") or "200"),
                    str(payload.get("bsr_code") or ""),
                    str(payload.get("chq_no") or ""),
                    tds_total,
                    total_amt,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                """
                UPDATE document_charge
                SET tds_challan_id = NULL, challan_no = NULL
                WHERE tds_challan_id = ?
                """,
                (challan_id,),
            )
            for charge_id in charge_ids:
                connection.execute(
                    """
                    UPDATE document_charge
                    SET tds_challan_id = ?, challan_no = ?
                    WHERE document_charge_id = ?
                    """,
                    (challan_id, challan_no, charge_id),
                )
        return self.get_challan_entry(financial_year_id, challan_id=challan_id)

    def delete_challan_entry(self, financial_year_id: str, challan_id: str) -> dict[str, str]:
        clean = challan_id.strip()
        if not clean:
            raise ValidationError("Challan id is required")
        with self.databases.connect(self.database_path) as connection:
            exists = connection.execute(
                "SELECT 1 FROM tds_challan WHERE tds_challan_id = ? AND financial_year_id = ?",
                (clean, financial_year_id),
            ).fetchone()
            if exists is None:
                raise ValidationError("TDS challan not found")
            connection.execute(
                """
                UPDATE document_charge
                SET tds_challan_id = NULL, challan_no = NULL
                WHERE tds_challan_id = ?
                """,
                (clean,),
            )
            connection.execute(
                "DELETE FROM tds_challan WHERE tds_challan_id = ?",
                (clean,),
            )
        return {"challan_id": clean, "status": "deleted"}

    def _row_to_form(self, row: dict[str, Any], lines: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "challan_id": str(row["tds_challan_id"]),
            "challan_display_id": str(row["challan_display_id"]),
            "challan_date": str(row["challan_date"]),
            "nature": str(row.get("nature") or ""),
            "filter_date_from": str(row["filter_date_from"]),
            "filter_date_to": str(row["filter_date_to"]),
            "deductee_code": str(row.get("deductee_code") or "All"),
            "challan_no": str(row.get("challan_no") or ""),
            "minor_head": str(row.get("minor_head") or "200"),
            "bsr_code": str(row.get("bsr_code") or ""),
            "chq_no": str(row.get("chq_no") or ""),
            "tds_total_amt": f"{int(row['tds_total_paise']) / 100:.2f}",
            "total_amt": f"{int(row['total_amt_paise']) / 100:.2f}",
            "lines": lines,
        }
