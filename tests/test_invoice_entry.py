"""Invoice (sale invoice) entry screen backend."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.invoice_entry import InvoiceEntryService


def test_invoice_entry_save_and_find(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "invoice_entry")
    databases.initialize()
    company = databases.create_company("Invoice Entry Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    sales = accounting.create_account("Sales", "income")
    party_account = accounting.create_account("Buyer Party", "party")
    party = accounting.create_party(
        "Invoice Buyer",
        "customer",
        account_id=party_account["account_id"],
        gstin="06ABCDE1234F1Z5",
    )
    commodity = accounting.create_commodity("MAIZE", hsn_code="1005")

    service = InvoiceEntryService(databases, company_id)
    saved = service.save_invoice_entry(
        year_id,
        {
            "entry_date": "2026-10-27",
            "book_no": "S-TEST-1",
            "bill_no": "B-200",
            "party_id": party["party_id"],
            "lines": [
                {
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "MAIZE",
                    "item_desc": "MAIZE",
                    "gross_wt": "10",
                    "tare": "0.5",
                    "shortage": "0",
                    "rate": "2100",
                    "cgst_pct": "2.5",
                    "sgst_pct": "2.5",
                    "igst_pct": "0",
                }
            ],
        },
    )
    assert saved["bill_no"] == "B-200"
    assert saved["lines"][0]["amount"] == "19950.00"
    assert float(saved["lines"][0]["gst_amt"]) == 997.5
    assert sales["account_id"]

    loaded = service.get_invoice_entry(
        year_id,
        entry_date="2026-10-27",
        party_id=party["party_id"],
        bill_no="B-200",
    )
    assert loaded["document_id"] == saved["document_id"]
