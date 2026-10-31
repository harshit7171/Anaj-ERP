"""GST expense voucher entry backend."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.gst_expense_voucher_entry import GstExpenseVoucherEntryService


def test_gst_expense_voucher_save_and_find(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "gev")
    databases.initialize()
    company = databases.create_company("GEV Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    accounting.create_account("GST Expense", "expense")
    party_account = accounting.create_account("Vendor", "party")
    party = accounting.create_party(
        "Expense Vendor",
        "supplier",
        account_id=party_account["account_id"],
    )
    commodity = accounting.create_commodity("FREIGHT SVC", hsn_code="9965")

    service = GstExpenseVoucherEntryService(databases, company_id)
    saved = service.save_gst_expense_voucher_entry(
        year_id,
        {
            "entry_date": "2026-10-27",
            "voucher_no": "GEV-TEST-1",
            "party_id": party["party_id"],
            "input_claim": "Y",
            "tds_pct": "2",
            "lines": [
                {
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "FREIGHT SVC",
                    "qty": "1",
                    "rate": "5000",
                    "cgst_pct": "9",
                    "sgst_pct": "9",
                }
            ],
        },
    )
    assert saved["voucher_no"] == "GEV-TEST-1"

    loaded = service.get_gst_expense_voucher_entry(
        year_id,
        entry_date="2026-10-27",
        party_id=party["party_id"],
        voucher_no="GEV-TEST-1",
    )
    assert loaded["document_id"] == saved["document_id"]
