"""Mandi purchase entry screen backend."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.mandi_purchase_entry import MandiPurchaseEntryService


def test_mandi_purchase_entry_save_and_find(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "mandi_entry")
    databases.initialize()
    company = databases.create_company("Mandi Entry Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    purchase = accounting.create_account("Mandi Purchase", "expense")
    party_account = accounting.create_account("Purchase Party", "party")
    purchase_party = accounting.create_party(
        "PADDY BASMATI PURCHASE",
        "supplier",
        account_id=party_account["account_id"],
    )
    line_party = accounting.create_party("MANOJ TRADING CO", "supplier")
    commodity = accounting.create_commodity("PADDY 1121 35KG")

    service = MandiPurchaseEntryService(databases, company_id)
    saved = service.save_mandi_purchase_entry(
        year_id,
        {
            "entry_date": "2026-10-27",
            "document_number": "MP-TEST-1",
            "purchase_party_id": purchase_party["party_id"],
            "mandi_city": "KURUKHETRA",
            "exp_master": "PADDY BASMATI EXP",
            "tds_rate": "2.00",
            "lines": [
                {
                    "line_party_id": line_party["party_id"],
                    "party_name": "MANOJ TRADING CO",
                    "bill_no": "101",
                    "due_date": "27/10/2026",
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "PADDY 1121 35KG",
                    "nugs": "150",
                    "weight": "52.500",
                    "rate": "3100",
                    "r_off": "N",
                    "tds_on": "N",
                }
            ],
        },
    )
    assert saved["document_number"] == "MP-TEST-1"
    assert saved["lines"][0]["bill_amt"] == "162750.00"
    assert purchase["account_id"]

    loaded = service.get_mandi_purchase_entry(
        year_id,
        entry_date="2026-10-27",
        purchase_party_id=purchase_party["party_id"],
        line_bill_no="101",
    )
    assert loaded["document_id"] == saved["document_id"]
