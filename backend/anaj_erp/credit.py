"""Farmer borrowing limits and credit exposure checks."""

from __future__ import annotations

from typing import Any

import json
from datetime import date
from decimal import Decimal

from .database import DatabaseManager
from .errors import ValidationError
from .mandi_business import calculate_vyaj_interest
from .mandi_business import merge_company_settings


class CreditLimitService:
    """Evaluate party ledger exposure against configured borrowing limits."""

    APPROACHING_THRESHOLD = 0.80

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        """Resolve the active company database."""
        self.databases = databases
        self.database_path = databases.company_path(company_id)

    def party_id_for_account(self, connection: Any, account_id: str) -> str | None:
        """Resolve a party from its linked ledger account, if any."""
        row = connection.execute(
            """
            SELECT party_id FROM party
            WHERE account_id = ? AND is_deleted = 0
            """,
            (account_id,),
        ).fetchone()
        return str(row["party_id"]) if row is not None else None

    def party_ledger_balance_paise(
        self,
        connection: Any,
        *,
        party_id: str,
        financial_year_id: str,
    ) -> int:
        """Return signed ledger balance for a party's linked account (Dr positive)."""
        row = connection.execute(
            """
            SELECT account_id, credit_limit_paise FROM party
            WHERE party_id = ? AND is_deleted = 0
            """,
            (party_id,),
        ).fetchone()
        if row is None:
            raise ValidationError("Party does not exist")
        account_id = row["account_id"]
        if account_id is None:
            return 0
        account = connection.execute(
            """
            SELECT opening_debit_paise, opening_credit_paise
            FROM account WHERE account_id = ? AND is_deleted = 0
            """,
            (account_id,),
        ).fetchone()
        if account is None:
            return 0
        movement = connection.execute(
            """
            SELECT
                COALESCE(SUM(vl.debit_paise), 0) AS debit_paise,
                COALESCE(SUM(vl.credit_paise), 0) AS credit_paise
            FROM voucher_line vl
            JOIN voucher v ON v.voucher_id = vl.voucher_id
            WHERE vl.account_id = ?
                AND v.financial_year_id = ?
                AND v.status IN ('posted', 'reversed')
            """,
            (account_id, financial_year_id),
        ).fetchone()
        opening = int(account["opening_debit_paise"]) - int(account["opening_credit_paise"])
        posted = int(movement["debit_paise"]) - int(movement["credit_paise"])
        return opening + posted

    def cash_advances_paise(
        self,
        connection: Any,
        *,
        party_id: str,
        financial_year_id: str,
    ) -> int:
        """Sum cash advances on posted documents not yet fully adjusted."""
        row = connection.execute(
            """
            SELECT COALESCE(SUM(advance_cash_paise), 0) AS advances
            FROM document
            WHERE party_id = ? AND financial_year_id = ?
                AND status = 'posted' AND advance_cash_paise > 0
            """,
            (party_id, financial_year_id),
        ).fetchone()
        return int(row["advances"]) if row else 0

    def pending_interest_paise(
        self,
        connection: Any,
        *,
        party_id: str,
        financial_year_id: str,
        as_of: date | None = None,
    ) -> int:
        """Accrued vyaj on outstanding debit balance when enabled in settings."""
        row = connection.execute(
            "SELECT settings_json FROM company_settings WHERE settings_key = 'default'"
        ).fetchone()
        settings = merge_company_settings(
            {} if row is None else json.loads(str(row["settings_json"] or "{}"))
        )
        if not settings.get("features", {}).get("interest_on_advances", True):
            return 0
        party = connection.execute(
            """
            SELECT p.account_id, a.metadata_json
            FROM party p
            LEFT JOIN account a ON a.account_id = p.account_id
            WHERE p.party_id = ? AND p.is_deleted = 0
            """,
            (party_id,),
        ).fetchone()
        if party is None:
            return 0
        metadata = json.loads(str(party["metadata_json"] or "{}"))
        rate_str = str(metadata.get("interest_rate") or metadata.get("interest_rate_percent") or "0")
        try:
            rate = Decimal(rate_str)
        except Exception:
            rate = Decimal("0")
        balance = max(
            self.party_ledger_balance_paise(
                connection,
                party_id=party_id,
                financial_year_id=financial_year_id,
            ),
            0,
        )
        if balance <= 0 or rate <= 0:
            return 0
        today = as_of or date.today()
        year = connection.execute(
            """
            SELECT starts_on FROM financial_year WHERE financial_year_id = ?
            """,
            (financial_year_id,),
        ).fetchone()
        if year is None:
            return 0
        start = date.fromisoformat(str(year["starts_on"]))
        days = max((today - start).days, 1)
        mode = str(metadata.get("interest_mode") or "simple")
        return calculate_vyaj_interest(
            principal_paise=balance,
            annual_rate_percent=rate,
            days=days,
            mode=mode,
        )

    def evaluate_credit(
        self,
        *,
        party_id: str,
        financial_year_id: str,
        additional_debit_paise: int,
        connection: Any | None = None,
    ) -> dict[str, Any]:
        """Compare projected debit exposure against the configured limit."""
        if additional_debit_paise < 0:
            raise ValidationError("Additional debit amount cannot be negative")

        def evaluate(connection: Any) -> dict[str, Any]:
            party = connection.execute(
                """
                SELECT party_id, name, credit_limit_paise, account_id
                FROM party WHERE party_id = ? AND is_deleted = 0
                """,
                (party_id,),
            ).fetchone()
            if party is None:
                raise ValidationError("Party does not exist")
            limit_paise = int(party["credit_limit_paise"])
            ledger_balance = self.party_ledger_balance_paise(
                connection,
                party_id=party_id,
                financial_year_id=financial_year_id,
            )
            advances = self.cash_advances_paise(
                connection,
                party_id=party_id,
                financial_year_id=financial_year_id,
            )
            interest = self.pending_interest_paise(
                connection,
                party_id=party_id,
                financial_year_id=financial_year_id,
            )
            current_balance = ledger_balance + advances + interest
            return self._build_evaluation(
                party_id=str(party["party_id"]),
                party_name=str(party["name"]),
                limit_paise=limit_paise,
                current_balance=current_balance,
                additional_debit_paise=additional_debit_paise,
                ledger_balance_paise=ledger_balance,
                cash_advances_paise=advances,
                pending_interest_paise=interest,
            )

        if connection is not None:
            return evaluate(connection)
        with self.databases.connect(self.database_path) as owned:
            return evaluate(owned)

    @staticmethod
    def _build_evaluation(
        *,
        party_id: str,
        party_name: str,
        limit_paise: int,
        current_balance: int,
        additional_debit_paise: int,
        ledger_balance_paise: int | None = None,
        cash_advances_paise: int = 0,
        pending_interest_paise: int = 0,
    ) -> dict[str, Any]:
        """Return a normalized credit evaluation payload."""
        projected = current_balance + additional_debit_paise
        if limit_paise <= 0:
            return {
                "party_id": party_id,
                "party_name": party_name,
                "credit_limit_paise": 0,
                "current_balance_paise": current_balance,
                "ledger_balance_paise": ledger_balance_paise or current_balance,
                "cash_advances_paise": cash_advances_paise,
                "pending_interest_paise": pending_interest_paise,
                "additional_debit_paise": additional_debit_paise,
                "projected_balance_paise": projected,
                "available_credit_paise": None,
                "overage_paise": 0,
                "status": "normal",
                "limit_assigned": False,
                "breached": False,
            }
        available = max(limit_paise - max(current_balance, 0), 0)
        overage = max(projected - limit_paise, 0)
        utilization = projected / limit_paise if limit_paise else 0.0
        if overage > 0:
            status = "exceeded"
        elif utilization >= CreditLimitService.APPROACHING_THRESHOLD:
            status = "approaching"
        else:
            status = "normal"
        return {
            "party_id": party_id,
            "party_name": party_name,
            "credit_limit_paise": limit_paise,
            "current_balance_paise": current_balance,
            "ledger_balance_paise": ledger_balance_paise or current_balance,
            "cash_advances_paise": cash_advances_paise,
            "pending_interest_paise": pending_interest_paise,
            "additional_debit_paise": additional_debit_paise,
            "projected_balance_paise": projected,
            "available_credit_paise": available,
            "overage_paise": overage,
            "status": status,
            "limit_assigned": True,
            "breached": overage > 0,
        }

    def list_farmer_credit_dashboard(
        self,
        financial_year_id: str,
        *,
        group: str = "",
        query: str = "",
    ) -> list[dict[str, Any]]:
        """Return farmer credit rows for the dashboard."""
        results: list[dict[str, Any]] = []
        clean_group = group.strip().lower()
        clean_query = query.strip().lower()
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    party_id, name, father_name, related_name,
                    agricultural_group, village_name, credit_limit_paise, account_id
                FROM party
                WHERE is_deleted = 0 AND party_type = 'farmer'
                ORDER BY agricultural_group COLLATE NOCASE, name COLLATE NOCASE
                """
            ).fetchall()
            for row in rows:
                father = str(row["father_name"] or row["related_name"] or "")
                label = " ".join(
                    part
                    for part in (
                        str(row["name"]),
                        father,
                        str(row["agricultural_group"] or ""),
                        str(row["village_name"] or ""),
                    )
                    if part
                ).lower()
                if clean_group and str(row["agricultural_group"] or "").lower() != clean_group:
                    continue
                if clean_query and clean_query not in label:
                    continue
                limit_paise = int(row["credit_limit_paise"])
                evaluation = self.evaluate_credit(
                    party_id=str(row["party_id"]),
                    financial_year_id=financial_year_id,
                    additional_debit_paise=0,
                    connection=connection,
                )
                results.append(
                    {
                        "party_id": str(row["party_id"]),
                        "group_name": str(row["agricultural_group"] or "—"),
                        "farmer_name": str(row["name"]),
                        "father_name": father or "—",
                        "village_name": str(row["village_name"] or "—"),
                        "current_balance_paise": evaluation["current_balance_paise"],
                        "credit_limit_paise": limit_paise,
                        "available_credit_paise": evaluation["available_credit_paise"],
                        "status": evaluation["status"],
                        "limit_assigned": limit_paise > 0,
                    }
                )
        return results
