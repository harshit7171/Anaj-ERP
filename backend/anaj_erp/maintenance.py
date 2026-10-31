"""Pilot migration validation and accounting reconciliation utilities."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .accounting import AccountingService
from .backup import BackupService
from .database import DatabaseManager
from .documents import DocumentService
from .errors import ValidationError


class MaintenanceService:
    """Provide dry-run imports and release/pilot reconciliation checks."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        """Resolve services for one company."""
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.accounting = AccountingService(databases, company_id)
        self.documents = DocumentService(databases, company_id)

    def import_master_csv(
        self,
        entity_type: str,
        source: Path,
        *,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Validate or import party, account or commodity CSV rows."""
        if entity_type not in {"account", "party", "commodity"}:
            raise ValidationError("Unsupported master import type")
        try:
            with source.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
        except OSError as exc:
            raise ValidationError(f"Could not read migration file: {exc}") from exc
        errors: list[dict[str, Any]] = []
        validated: list[dict[str, str]] = []
        for number, row in enumerate(rows, start=2):
            try:
                normalized = self._validate_row(entity_type, row)
                validated.append(normalized)
            except ValidationError as exc:
                errors.append({"row": number, "error": str(exc)})
        if errors:
            return {
                "dry_run": dry_run,
                "valid_rows": len(validated),
                "errors": errors,
                "imported": 0,
            }
        imported = 0
        if not dry_run:
            for row in validated:
                if entity_type == "account":
                    self.accounting.create_account(row["name"], row["account_type"])
                elif entity_type == "party":
                    self.accounting.create_party(
                        row["name"],
                        row["party_type"],
                        gstin=row.get("gstin", ""),
                        pan=row.get("pan", ""),
                        address=row.get("address", ""),
                        city=row.get("city", ""),
                        phone=row.get("phone", ""),
                    )
                else:
                    self.accounting.create_commodity(
                        row["name"],
                        variety=row.get("variety", ""),
                        hsn_code=row.get("hsn_code", ""),
                    )
                imported += 1
        return {
            "dry_run": dry_run,
            "valid_rows": len(validated),
            "errors": [],
            "imported": imported,
        }

    def reconcile(self, financial_year_id: str) -> dict[str, Any]:
        """Run database, voucher, stock and document consistency checks."""
        BackupService.integrity_check(self.database_path)
        with self.databases.connect(self.database_path) as connection:
            unbalanced = connection.execute(
                """
                SELECT v.voucher_id, v.voucher_number,
                    SUM(vl.debit_paise) AS debit_paise,
                    SUM(vl.credit_paise) AS credit_paise
                FROM voucher v
                JOIN voucher_line vl ON vl.voucher_id = v.voucher_id
                WHERE v.financial_year_id = ?
                GROUP BY v.voucher_id, v.voucher_number
                HAVING SUM(vl.debit_paise) != SUM(vl.credit_paise)
                """,
                (financial_year_id,),
            ).fetchall()
            missing_postings = connection.execute(
                """
                SELECT document_id, document_number
                FROM document
                WHERE financial_year_id = ?
                    AND status = 'posted'
                    AND document_type NOT IN (
                        'delivery_challan', 'transfer_challan', 'gate_pass',
                        'warehouse_transfer', 'packing_material_transfer'
                    )
                    AND posted_voucher_id IS NULL
                """,
                (financial_year_id,),
            ).fetchall()
            duplicate_movements = connection.execute(
                """
                SELECT idempotency_key, COUNT(*) AS count
                FROM inventory_movement
                WHERE financial_year_id = ?
                GROUP BY idempotency_key HAVING COUNT(*) > 1
                """,
                (financial_year_id,),
            ).fetchall()
        trial = self.accounting.trial_balance(financial_year_id)
        trial_difference = sum(int(row["balance_paise"]) for row in trial)
        stock = self.documents.stock_balance(financial_year_id)
        issues = {
            "unbalanced_vouchers": [dict(row) for row in unbalanced],
            "missing_document_postings": [dict(row) for row in missing_postings],
            "duplicate_inventory_movements": [dict(row) for row in duplicate_movements],
            "trial_difference_paise": trial_difference,
        }
        passed = (
            not unbalanced
            and not missing_postings
            and not duplicate_movements
            and trial_difference == 0
        )
        return {
            "passed": passed,
            "issues": issues,
            "trial_rows": len(trial),
            "stock_rows": len(stock),
        }

    @staticmethod
    def _validate_row(
        entity_type: str,
        row: dict[str, str | None],
    ) -> dict[str, str]:
        """Normalize one CSV row before any database writes."""
        normalized = {
            key: (value or "").strip()
            for key, value in row.items()
            if key is not None
        }
        if not normalized.get("name"):
            raise ValidationError("Name is required")
        if entity_type == "account" and not normalized.get("account_type"):
            raise ValidationError("account_type is required")
        if entity_type == "party" and not normalized.get("party_type"):
            raise ValidationError("party_type is required")
        gstin = normalized.get("gstin", "")
        if gstin and len(gstin) != 15:
            raise ValidationError("GSTIN must contain 15 characters")
        return normalized
