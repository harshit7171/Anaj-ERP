"""Search menu screens backend."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.search_screens import SearchScreensService


def test_account_search_and_copy(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "search")
    databases.initialize()
    company = databases.create_company("Search Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    account = accounting.create_account("Searchable Ledger", "expense")
    service = SearchScreensService(databases, company_id)
    result = service.search_accounts(year_id, {"ac_name": "Searchable", "row_limit": 50})
    assert result["total"] >= 1
    assert any(row["account_id"] == account["account_id"] for row in result["rows"])

    copied = service.copy_account(str(account["account_id"]), "Searchable Copy")
    assert copied["account_name"] == "Searchable Copy"


def test_stock_adjustment_multi_line(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "stk")
    databases.initialize()
    company = databases.create_company("Stock Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    item = accounting.create_commodity("WHEAT", hsn_code="1001")
    service = SearchScreensService(databases, company_id)
    saved = service.save_stock_adjustment(
        year_id,
        {
            "adjustment_date": "2026-10-27",
            "ref_no": "2",
            "godown": "Main",
            "lines": [
                {
                    "commodity_id": item["commodity_id"],
                    "item_name": "WHEAT",
                    "rec_qty": "10",
                }
            ],
        },
    )
    assert saved["ref_no"] == "2"
    loaded = service.get_stock_adjustment(year_id, ref_no="2", adjustment_date="2026-10-27")
    assert loaded["adjustment_id"] == saved["adjustment_id"]
    assert len(loaded["lines"]) == 1


def test_depreciation_and_letterhead(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "dep")
    databases.initialize()
    company = databases.create_company("Dep Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    account = accounting.create_account("Plant & Machinery", "asset")
    with databases.connect(databases.company_path(company_id)) as connection:
        connection.execute(
            "UPDATE account SET metadata_json = ? WHERE account_id = ?",
            ('{"depreciation_rate":"10","group_name":"Fixed Assets"}', account["account_id"]),
        )

    service = SearchScreensService(databases, company_id)
    rows = service.depreciation_chart(year_id, round_off=True)
    assert len(rows) >= 1

    options = service.get_letterhead_options()
    assert "options" in options
    saved = service.save_letterhead_options({"show_address": True})
    assert saved["options"]["show_address"] is True
