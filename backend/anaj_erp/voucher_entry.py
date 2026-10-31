"""Legacy Voucher Entry (Receipt / Payment / Contra / Journal) with grid lines."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .database import utc_now
from .errors import ValidationError
from .reports import ReportService

UI_MARKER = "voucher_entry_ui"


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception as exc:
        raise ValidationError("Invalid number") from exc


def _money_paise(value: Any) -> int:
    return int((_dec(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class VoucherEntryService:
    """Receipt/Payment style voucher with cash/bank header and amount grid."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.accounting = AccountingService(databases, company_id)
        self.reports = ReportService(databases, company_id)

    def lookup_accounts(self, query: str = "", limit: int = 40) -> list[dict[str, Any]]:
        clean = str(query or "").strip()
        prefix = f"{clean}%"
        contains = f"%{clean}%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT account_id, name AS account_name, account_type
                FROM account
                WHERE is_deleted = 0
                  AND (name LIKE ? COLLATE NOCASE OR name LIKE ? COLLATE NOCASE)
                ORDER BY
                    CASE WHEN name LIKE ? COLLATE NOCASE THEN 0 ELSE 1 END,
                    name COLLATE NOCASE
                LIMIT ?
                """,
                (prefix, contains, prefix, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def lookup_bank_accounts(self, query: str = "", limit: int = 40) -> list[dict[str, Any]]:
        clean = str(query or "").strip()
        prefix = f"{clean}%"
        contains = f"%{clean}%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT account_id, name AS bank_name, account_type
                FROM account
                WHERE is_deleted = 0
                  AND account_type IN ('bank', 'cash')
                  AND (name LIKE ? COLLATE NOCASE OR name LIKE ? COLLATE NOCASE)
                ORDER BY name COLLATE NOCASE
                LIMIT ?
                """,
                (prefix, contains, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def account_balance_paise(
        self,
        financial_year_id: str,
        account_id: str,
        as_of_date: str,
    ) -> int:
        if not account_id.strip():
            return 0
        year_start = self._financial_year_start(as_of_date)
        ledger = self.reports.account_ledger(
            financial_year_id,
            account_id,
            year_start,
            as_of_date,
        )
        return int(ledger["closing_balance_paise"])

    def cash_in_hand_paise(self, financial_year_id: str, as_of_date: str) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            cash = connection.execute(
                """
                SELECT account_id, name
                FROM account
                WHERE is_deleted = 0 AND account_type = 'cash'
                ORDER BY name COLLATE NOCASE
                LIMIT 1
                """
            ).fetchone()
        if cash is None:
            return {"cash_account_id": "", "cash_in_hand_paise": 0}
        balance = self.account_balance_paise(
            financial_year_id,
            str(cash["account_id"]),
            as_of_date,
        )
        return {
            "cash_account_id": str(cash["account_id"]),
            "cash_account_name": str(cash["name"]),
            "cash_in_hand_paise": balance,
        }

    def last_line_hints(
        self,
        financial_year_id: str,
        account_id: str,
    ) -> dict[str, str]:
        if not account_id.strip():
            return {}
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT vl.narration, vl.line_metadata_json
                FROM voucher_line vl
                JOIN voucher v ON v.voucher_id = vl.voucher_id
                WHERE v.financial_year_id = ?
                  AND vl.account_id = ?
                  AND v.status = 'posted'
                  AND json_extract(COALESCE(v.entry_metadata_json, '{}'), '$.ui') = ?
                ORDER BY v.voucher_date DESC, v.created_at DESC
                LIMIT 1
                """,
                (financial_year_id, account_id, UI_MARKER),
            ).fetchone()
        if row is None:
            return {}
        meta = json.loads(str(row["line_metadata_json"] or "{}"))
        return {
            "narration": str(row["narration"] or meta.get("narration") or ""),
            "due_date": str(meta.get("due_date") or ""),
            "cheque_no": str(meta.get("cheque_no") or ""),
        }

    def next_voucher_number(self, financial_year_id: str, voucher_type: str) -> str:
        clean_type = str(voucher_type or "Receipt").strip() or "Receipt"
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT voucher_number FROM voucher
                WHERE financial_year_id = ? AND voucher_type = ?
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (financial_year_id, clean_type),
            ).fetchall()
        max_num = 0
        for item in row:
            text = str(item["voucher_number"])
            digits = "".join(ch for ch in text if ch.isdigit())
            if digits:
                max_num = max(max_num, int(digits))
        return str(max_num + 1 if max_num else 1)

    def get_voucher_entry(
        self,
        financial_year_id: str,
        *,
        voucher_id: str = "",
        voucher_number: str = "",
        voucher_date: str = "",
        voucher_type: str = "",
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            row = None
            if voucher_id.strip():
                row = connection.execute(
                    """
                    SELECT * FROM voucher
                    WHERE voucher_id = ? AND financial_year_id = ?
                    """,
                    (voucher_id.strip(), financial_year_id),
                ).fetchone()
            elif voucher_number.strip() and voucher_date.strip():
                params: list[Any] = [
                    financial_year_id,
                    voucher_date.strip(),
                    voucher_number.strip(),
                ]
                type_sql = ""
                if voucher_type.strip():
                    type_sql = " AND voucher_type = ?"
                    params.append(voucher_type.strip())
                row = connection.execute(
                    f"""
                    SELECT * FROM voucher
                    WHERE financial_year_id = ?
                      AND voucher_date = ?
                      AND voucher_number = ?
                    {type_sql}
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
            if row is None:
                raise ValidationError("Voucher not found")
            meta = json.loads(str(row["entry_metadata_json"] or "{}"))
            if meta.get("ui") != UI_MARKER:
                raise ValidationError("Voucher was not created from Voucher Entry screen")
            lines = connection.execute(
                """
                SELECT vl.*, a.name AS account_name
                FROM voucher_line vl
                JOIN account a ON a.account_id = vl.account_id
                WHERE vl.voucher_id = ?
                ORDER BY vl.line_number
                """,
                (str(row["voucher_id"]),),
            ).fetchall()
        return self._row_to_form(dict(row), meta, [dict(line) for line in lines])

    def save_voucher_entry(self, financial_year_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        voucher_id = str(payload.get("voucher_id") or "").strip()
        if voucher_id:
            self.delete_voucher_entry(financial_year_id, voucher_id)
        voucher_type = str(payload.get("voucher_type") or "Receipt").strip()
        voucher_date = str(payload.get("voucher_date") or "").strip()
        if not voucher_date:
            raise ValidationError("Voucher date is required")
        voucher_number = str(payload.get("voucher_number") or "").strip()
        if not voucher_number:
            voucher_number = self.next_voucher_number(financial_year_id, voucher_type)
        payment_mode = str(payload.get("payment_mode") or "Cash").strip()
        header_account_id = str(payload.get("header_account_id") or "").strip()
        if not header_account_id:
            if payment_mode.lower() == "bank":
                raise ValidationError("Bank account is required")
            cash = self.cash_in_hand_paise(financial_year_id, voucher_date)
            header_account_id = str(cash.get("cash_account_id") or "")
        if not header_account_id:
            raise ValidationError("Cash account is not configured")
        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list):
            raise ValidationError("Lines are required")
        ui_lines: list[dict[str, Any]] = []
        total_net = 0
        for raw in raw_lines:
            if not isinstance(raw, dict):
                continue
            account_id = str(raw.get("account_id") or "").strip()
            amount_paise = _money_paise(raw.get("amount"))
            discount_paise = _money_paise(raw.get("discount"))
            net = amount_paise - discount_paise
            if not account_id or net <= 0:
                continue
            ui_lines.append(
                {
                    "account_id": account_id,
                    "account_name": str(raw.get("account_name") or ""),
                    "narration": str(raw.get("narration") or ""),
                    "amount_paise": amount_paise,
                    "discount_paise": discount_paise,
                    "net_paise": net,
                    "due_date": str(raw.get("due_date") or ""),
                    "cheque_no": str(raw.get("cheque_no") or ""),
                }
            )
            total_net += net
        if not ui_lines or total_net <= 0:
            raise ValidationError("Enter at least one line with amount")
        ledger_lines: list[dict[str, Any]] = []
        if voucher_type == "Receipt":
            ledger_lines.append(
                {"account_id": header_account_id, "debit_paise": total_net, "credit_paise": 0}
            )
            for line in ui_lines:
                ledger_lines.append(
                    {
                        "account_id": line["account_id"],
                        "debit_paise": 0,
                        "credit_paise": line["net_paise"],
                    }
                )
        elif voucher_type == "Payment":
            ledger_lines.append(
                {"account_id": header_account_id, "debit_paise": 0, "credit_paise": total_net}
            )
            for line in ui_lines:
                ledger_lines.append(
                    {
                        "account_id": line["account_id"],
                        "debit_paise": line["net_paise"],
                        "credit_paise": 0,
                    }
                )
        elif voucher_type == "Contra":
            if len(ui_lines) != 1:
                raise ValidationError("Contra requires exactly one counter line")
            counter = ui_lines[0]
            ledger_lines.append(
                {"account_id": header_account_id, "debit_paise": total_net, "credit_paise": 0}
            )
            ledger_lines.append(
                {
                    "account_id": counter["account_id"],
                    "debit_paise": 0,
                    "credit_paise": total_net,
                }
            )
        else:
            for line in ui_lines:
                side = str(line.get("entry_side") or payload.get("journal_side") or "Dr")
                if side.upper().startswith("C"):
                    ledger_lines.append(
                        {
                            "account_id": line["account_id"],
                            "debit_paise": 0,
                            "credit_paise": line["net_paise"],
                        }
                    )
                else:
                    ledger_lines.append(
                        {
                            "account_id": line["account_id"],
                            "debit_paise": line["net_paise"],
                            "credit_paise": 0,
                        }
                    )
        narration = str(payload.get("narration") or "").strip()
        if not narration:
            narration = "; ".join(
                part
                for part in [line["narration"] for line in ui_lines if line["narration"]]
                if part
            )[:500]
        posted = self.accounting.post_voucher(
            financial_year_id=financial_year_id,
            voucher_type=voucher_type,
            voucher_number=voucher_number,
            voucher_date=voucher_date,
            narration=narration,
            lines=ledger_lines,
            credit_override_confirmed=bool(payload.get("credit_override_confirmed")),
            manager_override_pin=str(payload.get("manager_override_pin") or ""),
        )
        new_voucher_id = str(posted["voucher_id"])
        entry_meta = {
            "ui": UI_MARKER,
            "payment_mode": payment_mode,
            "header_account_id": header_account_id,
            "header_account_name": str(payload.get("header_account_name") or ""),
            "user_name": str(payload.get("user_name") or ""),
            "lines": ui_lines,
        }
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE voucher
                SET entry_metadata_json = ?, updated_at = ?
                WHERE voucher_id = ?
                """,
                (json.dumps(entry_meta), timestamp, new_voucher_id),
            )
            db_lines = connection.execute(
                """
                SELECT voucher_line_id, account_id, line_number
                FROM voucher_line
                WHERE voucher_id = ?
                ORDER BY line_number
                """,
                (new_voucher_id,),
            ).fetchall()
            ui_by_account = {line["account_id"]: line for line in ui_lines}
            for db_line in db_lines:
                account_id = str(db_line["account_id"])
                ui = ui_by_account.get(account_id)
                if ui is None:
                    if account_id == header_account_id:
                        continue
                    continue
                line_meta = {
                    "amount_paise": ui["amount_paise"],
                    "discount_paise": ui["discount_paise"],
                    "due_date": ui["due_date"],
                    "cheque_no": ui["cheque_no"],
                }
                connection.execute(
                    """
                    UPDATE voucher_line
                    SET narration = ?, line_metadata_json = ?
                    WHERE voucher_line_id = ?
                    """,
                    (ui["narration"], json.dumps(line_meta), str(db_line["voucher_line_id"])),
                )
        return self.get_voucher_entry(financial_year_id, voucher_id=new_voucher_id)

    def delete_voucher_entry(self, financial_year_id: str, voucher_id: str) -> dict[str, str]:
        clean = voucher_id.strip()
        if not clean:
            raise ValidationError("Voucher id is required")
        entry = self.get_voucher_entry(financial_year_id, voucher_id=clean)
        reversal_no = f"REV-{entry['voucher_number']}"
        self.accounting.reverse_voucher(
            clean,
            reversal_number=reversal_no,
            reversal_date=entry["voucher_date"],
        )
        return {"voucher_id": clean, "status": "reversed"}

    def _row_to_form(
        self,
        row: dict[str, Any],
        meta: dict[str, Any],
        db_lines: list[dict[str, Any]],
    ) -> dict[str, Any]:
        header_account_id = str(meta.get("header_account_id") or "")
        ui_lines = meta.get("lines")
        if not isinstance(ui_lines, list):
            ui_lines = []
        if not ui_lines:
            for line in db_lines:
                if str(line["account_id"]) == header_account_id:
                    continue
                line_meta = json.loads(str(line.get("line_metadata_json") or "{}"))
                amount = int(line_meta.get("amount_paise") or line["debit_paise"] or line["credit_paise"])
                ui_lines.append(
                    {
                        "account_id": str(line["account_id"]),
                        "account_name": str(line.get("account_name") or ""),
                        "narration": str(line.get("narration") or ""),
                        "amount": f"{amount / 100:.2f}",
                        "discount": f"{int(line_meta.get('discount_paise') or 0) / 100:.2f}",
                        "due_date": str(line_meta.get("due_date") or ""),
                        "cheque_no": str(line_meta.get("cheque_no") or ""),
                    }
                )
        return {
            "voucher_id": str(row["voucher_id"]),
            "voucher_number": str(row["voucher_number"]),
            "voucher_date": str(row["voucher_date"]),
            "voucher_type": str(row["voucher_type"]),
            "payment_mode": str(meta.get("payment_mode") or "Cash"),
            "header_account_id": header_account_id,
            "header_account_name": str(meta.get("header_account_name") or ""),
            "user_name": str(meta.get("user_name") or ""),
            "narration": str(row.get("narration") or ""),
            "lines": ui_lines,
        }

    @staticmethod
    def _financial_year_start(iso_date: str) -> str:
        from datetime import date

        parsed = date.fromisoformat(iso_date)
        year = parsed.year if parsed.month >= 4 else parsed.year - 1
        return f"{year}-04-01"
