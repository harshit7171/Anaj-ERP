"""Extended report catalog keys."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.report_catalog import ReportCatalog
from anaj_erp.reports import ReportService


def test_trial_balance_and_difference(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "rep")
    databases.initialize()
    company = databases.create_company("Rep Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    accounting.create_account("Cash", "cash")

    service = ReportService(databases, company_id)
    catalog = ReportCatalog(service)
    trial = catalog.run(year_id, "trial_balance", {})
    assert trial["rows"]

    diff = catalog.run(year_id, "trial_balance_difference", {})
    assert "difference_paise" in diff


def test_debit_note_register_key(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "dn")
    databases.initialize()
    company = databases.create_company("DN Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    service = ReportService(databases, company_id)
    catalog = ReportCatalog(service)
    rows = catalog.run(
        year_id,
        "debit_note_report",
        {"date_from": "2026-04-01", "date_to": "2026-10-27"},
    )
    assert "rows" in rows
