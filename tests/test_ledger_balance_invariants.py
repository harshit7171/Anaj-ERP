"""Ledger must balance to zero after each posting (Point 16)."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.documents import DocumentService


def _trial_debits_equal_credits(
    databases: DatabaseManager,
    company_id: str,
    year_id: str,
) -> bool:
    rows = AccountingService(databases, company_id).trial_balance(year_id)
    debits = sum(int(row.get("debit_paise") or 0) for row in rows)
    credits = sum(int(row.get("credit_paise") or 0) for row in rows)
    return debits == credits


def test_sale_and_purchase_keep_trial_balance_zero(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "balance")
    databases.initialize()
    company = databases.create_company("Balance Mandi", 2026)
    company_id = company["company_id"]
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])
    accounting = AccountingService(databases, company_id)
    sales = accounting.create_account("Sales", "income")
    purchase = accounting.create_account("Purchase", "expense")
    party_acc = accounting.create_account("Party", "party")
    party = accounting.create_party("Farmer", "supplier", account_id=party_acc["account_id"])
    commodity = accounting.create_commodity("Wheat", hsn_code="1001")
    documents = DocumentService(databases, company_id)

    documents.post(
        financial_year_id=year_id,
        document_type="sale_invoice",
        document_number="S-1",
        document_date="2026-05-01",
        party_id=party["party_id"],
        main_account_id=sales["account_id"],
        party_account_id=party_acc["account_id"],
        lines=[
            {
                "commodity_id": commodity["commodity_id"],
                "quantity_scaled": 5000,
                "quantity_scale": 3,
                "rate_paise": 20_000,
                "rate_unit": "quintal",
            }
        ],
        excluded_charge_codes=["DAMI", "LABOUR", "AUCTION", "MARKET_FEE", "HRDF", "SGST", "CGST"],
    )
    assert _trial_debits_equal_credits(databases, company_id, year_id)

    documents.post(
        financial_year_id=year_id,
        document_type="purchase_invoice",
        document_number="P-1",
        document_date="2026-05-02",
        party_id=party["party_id"],
        main_account_id=purchase["account_id"],
        party_account_id=party_acc["account_id"],
        lines=[
            {
                "commodity_id": commodity["commodity_id"],
                "quantity_scaled": 3000,
                "quantity_scale": 3,
                "rate_paise": 18_000,
                "rate_unit": "quintal",
            }
        ],
        excluded_charge_codes=["DAMI", "LABOUR", "AUCTION", "MARKET_FEE", "HRDF", "SGST", "CGST"],
    )
    assert _trial_debits_equal_credits(databases, company_id, year_id)
