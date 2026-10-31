"""GST menu report page layouts."""

from pathlib import Path

from anaj_erp.database import DatabaseManager
from anaj_erp.report_catalog import ReportCatalog
from anaj_erp.reports import ReportService


def test_gst_purchase_sale_summary_columns(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "gst")
    databases.initialize()
    company = databases.create_company("GST Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    service = ReportService(databases, company_id)
    catalog = ReportCatalog(service)
    result = catalog.run(
        year_id,
        "gst_purchase_sale_summary",
        {"date_from": "2026-04-01", "date_to": "2026-10-27", "transaction_type": "all"},
    )
    assert "columns" in result
    assert "Date" in result["columns"]
    assert "footer" in result
    assert "Grand Total" in result["footer"]


def test_gstr3b_section_rows(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "g3b")
    databases.initialize()
    company = databases.create_company("G3B Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    service = ReportService(databases, company_id)
    catalog = ReportCatalog(service)
    result = catalog.run(
        year_id,
        "gstr3b_summary",
        {"date_from": "2026-04-01", "date_to": "2026-10-27", "return_period": "2026-10"},
    )
    assert result["columns"][0] == "Nature of Supplies"
    assert any("3.1" in str(row.get("Nature of Supplies", "")) for row in result["rows"])
