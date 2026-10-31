"""Bank reconciliation — filter bank ledger lines and mark reconciled."""

from __future__ import annotations

import csv
import json
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from .database import DatabaseManager
from .errors import ValidationError
from .register_pdf import RegisterPdfPrinter


class BankReconciliationService:
    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)

    def search_lines(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        date_from = str(payload.get("date_from") or "").strip()
        date_to = str(payload.get("date_to") or "").strip()
        if not date_from or not date_to:
            raise ValidationError("Date from and date to are required")
        bank_name = str(payload.get("bank_name") or "").strip()
        dc_filter = str(payload.get("debit_credit") or "B").upper()
        recon_filter = str(payload.get("reconciled_filter") or "B").upper()
        amount_eq = self._optional_paise(payload.get("amount_eq"))
        amount_min = self._optional_paise(payload.get("amount_gte"))
        amount_max = self._optional_paise(payload.get("amount_lte"))
        particulars = str(payload.get("particulars") or "").strip()
        cheque = str(payload.get("cheque_no") or "").strip()

        params: list[Any] = [financial_year_id, date_from, date_to]
        bank_sql = ""
        if bank_name:
            bank_sql = " AND a.name LIKE ? COLLATE NOCASE"
            params.append(f"%{bank_name}%")
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    vl.voucher_line_id,
                    v.voucher_date,
                    v.voucher_type,
                    v.voucher_number,
                    a.name AS bank_name,
                    vl.debit_paise,
                    vl.credit_paise,
                    COALESCE(vl.narration, v.narration) AS particulars,
                    vl.line_metadata_json
                FROM voucher_line vl
                JOIN voucher v ON v.voucher_id = vl.voucher_id
                JOIN account a ON a.account_id = vl.account_id
                WHERE v.financial_year_id = ?
                  AND v.status = 'posted'
                  AND v.voucher_date BETWEEN ? AND ?
                  AND a.account_type IN ('bank', 'cash')
                  {bank_sql}
                ORDER BY v.voucher_date, v.voucher_number, vl.line_number
                """,
                params,
            ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            meta = json.loads(str(row["line_metadata_json"] or "{}"))
            reconciled = bool(meta.get("bank_reconciled"))
            debit = int(row["debit_paise"])
            credit = int(row["credit_paise"])
            if dc_filter == "D" and debit <= 0:
                continue
            if dc_filter == "C" and credit <= 0:
                continue
            if recon_filter == "R" and not reconciled:
                continue
            if recon_filter == "N" and reconciled:
                continue
            amount = debit if debit > 0 else credit
            if amount_eq is not None and amount != amount_eq:
                continue
            if amount_min is not None and amount < amount_min:
                continue
            if amount_max is not None and amount > amount_max:
                continue
            part_text = str(row["particulars"] or "")
            if particulars and particulars.lower() not in part_text.lower():
                continue
            cheque_no = str(meta.get("cheque_no") or "")
            if cheque and cheque not in cheque_no and cheque not in part_text:
                continue
            results.append(
                {
                    "voucher_line_id": str(row["voucher_line_id"]),
                    "voucher_date": str(row["voucher_date"]),
                    "voucher_type": str(row["voucher_type"]),
                    "voucher_number": str(row["voucher_number"]),
                    "bank_name": str(row["bank_name"]),
                    "debit": f"{debit / 100:.2f}",
                    "credit": f"{credit / 100:.2f}",
                    "particulars": part_text,
                    "cheque_no": cheque_no,
                    "reconciled": reconciled,
                }
            )
        return results

    def set_reconciled(
        self,
        financial_year_id: str,
        voucher_line_ids: list[str],
        reconciled: bool,
    ) -> dict[str, Any]:
        if not voucher_line_ids:
            raise ValidationError("No lines selected")
        with self.databases.connect(self.database_path) as connection:
            for line_id in voucher_line_ids:
                row = connection.execute(
                    """
                    SELECT vl.line_metadata_json
                    FROM voucher_line vl
                    JOIN voucher v ON v.voucher_id = vl.voucher_id
                    WHERE vl.voucher_line_id = ? AND v.financial_year_id = ?
                    """,
                    (line_id, financial_year_id),
                ).fetchone()
                if row is None:
                    continue
                meta = json.loads(str(row["line_metadata_json"] or "{}"))
                meta["bank_reconciled"] = reconciled
                connection.execute(
                    "UPDATE voucher_line SET line_metadata_json = ? WHERE voucher_line_id = ?",
                    (json.dumps(meta), line_id),
                )
        return {"updated": len(voucher_line_ids), "reconciled": reconciled}

    def export_excel_csv(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
    ) -> dict[str, str]:
        rows = self.search_lines(financial_year_id, payload)
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8-sig",
            newline="",
        )
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Date",
                "Voucher Type",
                "Voucher No",
                "Bank",
                "Debit",
                "Credit",
                "Particulars",
                "Cheque",
                "Reconciled",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["voucher_date"],
                    row["voucher_type"],
                    row["voucher_number"],
                    row["bank_name"],
                    row["debit"],
                    row["credit"],
                    row["particulars"],
                    row["cheque_no"],
                    "Yes" if row["reconciled"] else "No",
                ]
            )
        handle.close()
        return {"path": handle.name, "row_count": str(len(rows))}

    def print_report(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
        *,
        company_name: str = "Company",
    ) -> dict[str, str]:
        rows = self.search_lines(financial_year_id, payload)
        pdf_rows = [
            {
                "entry_date": row["voucher_date"],
                "voucher_number": row["voucher_number"],
                "account_name": f"{row['bank_name']} — {row['particulars'][:60]}",
                "debit_paise": int(Decimal(row["debit"]) * 100),
                "credit_paise": int(Decimal(row["credit"]) * 100),
            }
            for row in rows[:500]
        ]
        destination = Path(tempfile.gettempdir()) / f"bank-recon-{uuid.uuid4().hex}.pdf"
        RegisterPdfPrinter.day_book(
            company_name,
            pdf_rows,
            date_from=str(payload.get("date_from") or ""),
            date_to=str(payload.get("date_to") or ""),
            destination=destination,
        )
        RegisterPdfPrinter.print_path(destination)
        return {"path": str(destination), "row_count": str(len(pdf_rows))}

    @staticmethod
    def _optional_paise(value: Any) -> int | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return int((Decimal(text) * 100).to_integral_value())
        except Exception as exc:
            raise ValidationError("Invalid amount filter") from exc
