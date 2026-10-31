"""Foundation tests for fixed-point accounting and company storage."""

from decimal import Decimal
from pathlib import Path

import pytest

from anaj_erp.api import ApplicationApi
from anaj_erp.database import DatabaseManager
from anaj_erp.domain import ChargeBasis
from anaj_erp.domain import ChargeMode
from anaj_erp.domain import ChargeRule
from anaj_erp.domain import FinancialYear
from anaj_erp.domain import LedgerLine
from anaj_erp.domain import paise_to_rupees
from anaj_erp.domain import rupees_to_paise
from anaj_erp.domain import validate_balanced
from anaj_erp.errors import ValidationError


def test_money_conversion_uses_commercial_rounding() -> None:
    """Rupee conversion preserves exact paise and rounds half up."""
    assert rupees_to_paise("123.455") == 12346
    assert paise_to_rupees(12346) == "123.46"


def test_financial_year_runs_april_to_march() -> None:
    """Financial-year labels and boundaries follow the Indian convention."""
    year = FinancialYear(2026)
    assert year.label == "2026-2027"
    assert year.starts_on.isoformat() == "2026-04-01"
    assert year.ends_on.isoformat() == "2027-03-31"


def test_percentage_charge_calculates_integer_paise() -> None:
    """Configured percentage charges return deterministic integer paise."""
    rule = ChargeRule(
        code="COMMISSION",
        label="Commission",
        basis=ChargeBasis.AMOUNT,
        mode=ChargeMode.PERCENTAGE,
        rate=Decimal("1.00"),
    )
    assert rule.calculate(amount_paise=5_409_100) == 54_091


def test_fixed_bag_charge_uses_decimal_units() -> None:
    """Fixed bag rates avoid floating-point drift."""
    rule = ChargeRule(
        code="LAB_PACKING",
        label="Lab Pakki",
        basis=ChargeBasis.BAG,
        mode=ChargeMode.FIXED,
        rate=Decimal("8.50"),
    )
    assert rule.calculate(bags=Decimal("285")) == 242_250


def test_unbalanced_voucher_is_rejected() -> None:
    """Posting validation rejects unequal debit and credit totals."""
    lines = [
        LedgerLine(account_id="cash", debit_paise=10_000),
        LedgerLine(account_id="sales", credit_paise=9_999),
    ]
    with pytest.raises(ValidationError, match="not balanced"):
        validate_balanced(lines)


def test_balanced_voucher_is_accepted() -> None:
    """Equal debit and credit totals pass posting validation."""
    validate_balanced(
        [
            LedgerLine(account_id="cash", debit_paise=10_000),
            LedgerLine(account_id="sales", credit_paise=10_000),
        ]
    )


@pytest.fixture
def databases(tmp_path: Path) -> DatabaseManager:
    """Create an initialized isolated database manager."""
    manager = DatabaseManager(tmp_path / "data")
    manager.initialize()
    return manager


def test_company_creation_isolated_with_financial_year(
    databases: DatabaseManager,
) -> None:
    """Creating a company registers it and creates its first year."""
    company = databases.create_company("Aggarwal Brothers", 2026)
    companies = databases.list_companies()
    years = databases.list_financial_years(company["company_id"])

    assert companies[0]["name"] == "Aggarwal Brothers"
    assert years[0]["label"] == "2026-2027"
    assert years[0]["is_locked"] is False
    assert databases.company_path(company["company_id"]).exists()


def test_api_rejects_year_from_another_company(databases: DatabaseManager) -> None:
    """The desktop bridge cannot select a year across company boundaries."""
    first = databases.create_company("First Company", 2025)
    second = databases.create_company("Second Company", 2025)
    first_year = databases.list_financial_years(first["company_id"])[0]
    api = ApplicationApi(databases)

    result = api.select_context(
        second["company_id"],
        str(first_year["financial_year_id"]),
    )

    assert result["ok"] is False
    assert result["error_type"] == "ValidationError"
