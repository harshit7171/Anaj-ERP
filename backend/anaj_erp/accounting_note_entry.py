"""Simple Debit Note / Credit Note (non-GST) add/modify."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .database import utc_now
from .documents import DocumentService
from .errors import ValidationError

NOTE_KINDS = {"debit_note", "credit_note"}


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception as exc:
        raise ValidationError("Invalid number") from exc


def _money_paise(value: Any) -> int:
    return int((_dec(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class AccountingNoteEntryService:
    """Legacy debit/credit note with party header and ledger lines."""

    def __init__(self, databases: DatabaseManager, company_id: str, note_kind: str) -> None:
        clean = str(note_kind or "").strip()
        if clean not in NOTE_KINDS:
            raise ValidationError("Invalid note kind")
        self.note_kind = clean
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.documents = DocumentService(databases, company_id)
        self.accounting = AccountingService(databases, company_id)

    def get_note_entry(
        self,
        financial_year_id: str,
        *,
        document_id: str = "",
        note_date: str = "",
        party_id: str = "",
        note_no: str = "",
    ) -> dict[str, Any]:
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
                    (clean_id, self.note_kind),
                ).fetchone()
            else:
                if not note_date.strip() or not note_no.strip():
                    raise ValidationError("Note date and number are required to find an entry")
                params: list[Any] = [
                    financial_year_id,
                    self.note_kind,
                    note_date.strip(),
                    note_no.strip(),
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
                label = "Debit note" if self.note_kind == "debit_note" else "Credit note"
                raise ValidationError(f"{label} not found")
        meta = json.loads(str(row["header_metadata_json"] or "{}"))
        return self._row_to_form(dict(row), meta)

    def save_note_entry(self, financial_year_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = str(payload.get("document_id") or "").strip()
        if document_id:
            self.delete_note_entry(financial_year_id, document_id)
        party_id = str(payload.get("party_id") or "").strip()
        if not party_id:
            raise ValidationError("Party Name is required")
        note_date = str(payload.get("note_date") or "").strip()
        if not note_date:
            raise ValidationError("Note date is required")
        note_no = str(payload.get("note_no") or "").strip()
        if not note_no:
            note_no = self.documents.next_document_number(financial_year_id, self.note_kind)
        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ValidationError("At least one line is required")
        line_items: list[dict[str, Any]] = []
        total_paise = 0
        for raw in raw_lines:
            if not isinstance(raw, dict):
                continue
            account_id = str(raw.get("account_id") or "").strip()
            amount_paise = _money_paise(raw.get("amount"))
            if not account_id or amount_paise <= 0:
                continue
            line_items.append(
                {
                    "account_id": account_id,
                    "account_name": str(raw.get("account_name") or ""),
                    "particulars": str(raw.get("particulars") or ""),
                    "amount": f"{amount_paise / 100:.2f}",
                }
            )
            total_paise += amount_paise
        if not line_items or total_paise <= 0:
            raise ValidationError("At least one valid line with amount is required")
        with self.databases.connect(self.database_path) as connection:
            party = connection.execute(
                "SELECT account_id, name FROM party WHERE party_id = ? AND is_deleted = 0",
                (party_id,),
            ).fetchone()
            if party is None or not party["account_id"]:
                raise ValidationError("Party must have a linked ledger account")
            party_account_id = str(party["account_id"])
        voucher_lines: list[dict[str, Any]] = []
        if self.note_kind == "debit_note":
            voucher_lines.append(
                {"account_id": party_account_id, "debit_paise": total_paise, "credit_paise": 0}
            )
            for item in line_items:
                voucher_lines.append(
                    {
                        "account_id": item["account_id"],
                        "debit_paise": 0,
                        "credit_paise": _money_paise(item["amount"]),
                    }
                )
        else:
            voucher_lines.append(
                {"account_id": party_account_id, "debit_paise": 0, "credit_paise": total_paise}
            )
            for item in line_items:
                voucher_lines.append(
                    {
                        "account_id": item["account_id"],
                        "debit_paise": _money_paise(item["amount"]),
                        "credit_paise": 0,
                    }
                )
        refs = [
            str(payload.get("reference_1") or "").strip(),
            str(payload.get("reference_2") or "").strip(),
            str(payload.get("reference_3") or "").strip(),
        ]
        narration = "; ".join(
            part
            for part in [
                f"Party: {party['name']}",
                *[f"Ref{i + 1}: {ref}" for i, ref in enumerate(refs) if ref],
                *[line["particulars"] for line in line_items if line["particulars"]],
            ]
            if part
        )
        posted = self.accounting.post_voucher(
            financial_year_id=financial_year_id,
            voucher_type=self.note_kind,
            voucher_number=note_no,
            voucher_date=note_date,
            narration=narration[:500],
            lines=voucher_lines,
        )
        voucher_id = str(posted["voucher_id"])
        header_meta = {k: v for k, v in payload.items() if k not in {"lines", "document_id"}}
        header_meta["lines"] = line_items
        header_meta["note_no"] = note_no
        header_meta["voucher_id"] = voucher_id
        document_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO document(
                    document_id, financial_year_id, document_type, document_number,
                    document_date, party_id, status, due_date, reference_number, remarks,
                    grand_total_paise, header_metadata_json, posted_voucher_id,
                    calculation_snapshot_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'posted', ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                """,
                (
                    document_id,
                    financial_year_id,
                    self.note_kind,
                    note_no,
                    note_date,
                    party_id,
                    str(payload.get("due_date") or ""),
                    refs[0] or refs[1] or refs[2] or "",
                    str(payload.get("remarks") or ""),
                    total_paise,
                    json.dumps(header_meta),
                    voucher_id,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_note_entry(financial_year_id, document_id=document_id)

    def delete_note_entry(self, financial_year_id: str, document_id: str) -> dict[str, str]:
        clean = str(document_id or "").strip()
        if not clean:
            raise ValidationError("Document id is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT posted_voucher_id, document_date, document_number
                FROM document WHERE document_id = ? AND financial_year_id = ? AND document_type = ?
                """,
                (clean, financial_year_id, self.note_kind),
            ).fetchone()
            if row is None:
                raise ValidationError("Note entry not found")
            voucher_id = str(row["posted_voucher_id"] or "")
            document_date = str(row["document_date"])
            document_number = str(row["document_number"])
        if voucher_id:
            self.accounting.reverse_voucher(
                voucher_id,
                f"REV-{document_number}"[:24],
                document_date,
                f"{self.note_kind} modify or delete",
            )
        with self.databases.connect(self.database_path) as connection:
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

    def lookup_accounts(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT account_id, name FROM account
                WHERE is_deleted = 0 AND name LIKE ?
                ORDER BY name COLLATE NOCASE LIMIT 40
                """,
                (pattern,),
            ).fetchall()
        return [{"account_id": r["account_id"], "account_name": r["name"]} for r in rows]

    def lookup_items(self, query: str = "") -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%" if query.strip() else "%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT commodity_id, name AS item_name
                FROM commodity
                WHERE is_deleted = 0 AND name LIKE ?
                ORDER BY name COLLATE NOCASE LIMIT 30
                """,
                (pattern,),
            ).fetchall()
        return [dict(row) for row in rows]

    def next_entry_number(self, financial_year_id: str) -> str:
        return self.documents.next_document_number(financial_year_id, self.note_kind)

    @staticmethod
    def _row_to_form(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
        base = {
            "document_id": row["document_id"],
            "note_no": meta.get("note_no") or row.get("document_number") or "",
            "note_date": row.get("document_date") or "",
            "party_id": row.get("party_id") or "",
            "party_name": row.get("party_name") or meta.get("party_name") or "",
            "due_date": meta.get("due_date") or row.get("due_date") or "",
            "voucher_id": meta.get("voucher_id") or row.get("posted_voucher_id") or "",
            "lines": meta.get("lines") or [],
        }
        for key, value in meta.items():
            if key not in base:
                base[key] = value
        return base
