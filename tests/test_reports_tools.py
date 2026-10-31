"""Phase 5–7 report catalog and tools."""

from pathlib import Path

from anaj_erp.database import DatabaseManager
from anaj_erp.report_catalog import ReportCatalog
from anaj_erp.reports import ReportService
from anaj_erp.tools import ToolsService


def _company_context(tmp_path: Path) -> tuple[DatabaseManager, str, str]:
    databases = DatabaseManager(tmp_path / "data")
    databases.initialize()
    company = databases.create_company("Report Tools Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])
    return databases, company_id, year_id


def test_report_catalog_trial_balance(tmp_path: Path) -> None:
    databases, company_id, year_id = _company_context(tmp_path)
    catalog = ReportCatalog(ReportService(databases, company_id))
    result = catalog.run(year_id, "trial_balance", {})
    assert result["rows"] is not None


def test_gstr1_json_export_shape(tmp_path: Path) -> None:
    databases, company_id, year_id = _company_context(tmp_path)
    catalog = ReportCatalog(ReportService(databases, company_id))
    result = catalog.run(
        year_id,
        "gstr1_json",
        {"date_from": "2026-04-01", "date_to": "2026-03-31"},
    )
    assert "json" in result
    assert "export" in result
    assert result["export"]["version"]


def test_company_settings_round_trip(tmp_path: Path) -> None:
    databases, company_id, _year_id = _company_context(tmp_path)
    tools = ToolsService(databases, company_id)
    tools.save_company_settings({"gstin": "06ABCDE1234F1Z5", "legal_name": "Demo"})
    loaded = tools.get_company_settings()
    assert loaded["gstin"] == "06ABCDE1234F1Z5"
    assert loaded["legal_name"] == "Demo"


def test_find_accounts_empty_query(tmp_path: Path) -> None:
    databases, company_id, _year_id = _company_context(tmp_path)
    tools = ToolsService(databases, company_id)
    rows = tools.find_accounts()
    assert isinstance(rows, list)
