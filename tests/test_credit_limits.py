"""Tests for farmer credit limit evaluation."""

from pathlib import Path

import pytest

from anaj_erp.accounting import AccountingService
from anaj_erp.credit import CreditLimitService
from anaj_erp.database import DatabaseManager
from anaj_erp.errors import CreditLimitBreachedError


def setup_company(tmp_path: Path) -> tuple[DatabaseManager, str, str]:
    """Create one company and return manager, company id and year id."""
    databases = DatabaseManager(tmp_path / "credit")
    databases.initialize()
    company = databases.create_company("Credit Mandi", 2026)
    year = databases.list_financial_years(company["company_id"])[0]
    return databases, company["company_id"], str(year["financial_year_id"])


def test_zero_limit_means_unassigned(tmp_path: Path) -> None:
    """A zero credit limit must not block transactions."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    account = accounting.create_account("Farmer Ledger", "party")
    party = accounting.create_party(
        "Ram Singh",
        "farmer",
        account_id=account["account_id"],
        credit_limit_paise=0,
    )
    evaluation = CreditLimitService(databases, company_id).evaluate_credit(
        party_id=party["party_id"],
        financial_year_id=year_id,
        additional_debit_paise=500_000,
    )
    assert evaluation["limit_assigned"] is False
    assert evaluation["breached"] is False


def test_credit_limit_warning_and_override(tmp_path: Path) -> None:
    """Breached limits reject writes unless an explicit override is supplied."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    cash = accounting.create_account("Cash", "cash")
    farmer_account = accounting.create_account("Farmer", "party")
    accounting.create_party(
        "Suresh",
        "farmer",
        account_id=farmer_account["account_id"],
        credit_limit_paise=100_000,
    )
    with pytest.raises(CreditLimitBreachedError):
        accounting.post_voucher(
            financial_year_id=year_id,
            voucher_type="payment",
            voucher_number="P-1",
            voucher_date="2026-05-01",
            narration="Advance",
            lines=[
                {"account_id": farmer_account["account_id"], "debit_paise": 150_000},
                {"account_id": cash["account_id"], "credit_paise": 150_000},
            ],
        )
    posted = accounting.post_voucher(
        financial_year_id=year_id,
        voucher_type="payment",
        voucher_number="P-2",
        voucher_date="2026-05-01",
        narration="Advance override",
        lines=[
            {"account_id": farmer_account["account_id"], "debit_paise": 150_000},
            {"account_id": cash["account_id"], "credit_paise": 150_000},
        ],
        credit_override_confirmed=True,
    )
    assert posted["status"] == "posted"
