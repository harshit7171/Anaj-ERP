"""GST purchase entry screen backend."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.gst_purchase_entry import GstPurchaseEntryService


def test_gst_purchase_entry_save_and_find(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "gst_entry")
    databases.initialize()
    company = databases.create_company("GST Entry Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    purchase = accounting.create_account("GST Purchase", "expense")
    party_account = accounting.create_account("Supplier Party", "party")
    party = accounting.create_party(
        "GST Supplier",
        "supplier",
        account_id=party_account["account_id"],
        gstin="06ABCDE1234F1Z5",
    )
    commodity = accounting.create_commodity("WHEAT", hsn_code="1001")

    service = GstPurchaseEntryService(databases, company_id)
    saved = service.save_gst_purchase_entry(
        year_id,
        {
            "entry_date": "2026-10-27",
            "document_number": "GP-TEST-1",
            "party_id": party["party_id"],
            "bill_no": "B-100",
            "rev_charges": "N",
            "input_claim": "Y",
            "lines": [
                {
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "WHEAT",
                    "item_desc": "WHEAT",
                    "gross_wt": "10",
                    "tare": "0",
                    "adj_wt": "0",
                    "rate": "2000",
                    "hsn_code": "1001",
                    "cgst_pct": "2.5",
                    "sgst_pct": "2.5",
                    "igst_pct": "0",
                }
            ],
        },
    )
    assert saved["bill_no"] == "B-100"
    assert saved["lines"][0]["amount"] == "20000.00"
    assert float(saved["lines"][0]["gst_amt"]) == 1000.0
    assert purchase["account_id"]

    loaded = service.get_gst_purchase_entry(
        year_id,
        entry_date="2026-10-27",
        party_id=party["party_id"],
        bill_no="B-100",
    )
    assert loaded["document_id"] == saved["document_id"]
