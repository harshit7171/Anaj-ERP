"""Kachi purchase dedicated screen backend."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.kachi_purchase import KachiPurchaseService


def test_kachi_purchase_save_and_find(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "kachi")
    databases.initialize()
    company = databases.create_company("Kachi Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    purchase = accounting.create_account("Kachi Purchase", "expense")
    buyer_account = accounting.create_account("Buyer Ledger", "party")
    buyer = accounting.create_party("Main Buyer", "customer", account_id=buyer_account["account_id"])
    seller = accounting.create_party("Harshit A", "supplier")
    commodity = accounting.create_commodity("BARDANA")

    service = KachiPurchaseService(databases, company_id)
    saved = service.save_kachi_purchase(
        year_id,
        {
            "entry_date": "2026-10-27",
            "po_no": "1",
            "mandi": "KURUKHETRA",
            "lock_hours": "24",
            "buyer_party_id": buyer["party_id"],
            "lines": [
                {
                    "seller_party_id": seller["party_id"],
                    "seller_name": "Harshit A",
                    "slip_no": "1",
                    "bill_date": "27/10/2026",
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "BARDANA",
                    "bharti": "0",
                    "bags": "10",
                    "weight": "5.000",
                    "rate": "100",
                }
            ],
        },
    )
    assert saved["po_no"] == "1"
    assert saved["lines"][0]["amount"] == "500.00"
    assert purchase["account_id"]

    loaded = service.get_kachi_purchase(
        year_id,
        entry_date="2026-10-27",
        po_no="1",
        buyer_party_id=buyer["party_id"],
    )
    assert loaded["document_id"] == saved["document_id"]
