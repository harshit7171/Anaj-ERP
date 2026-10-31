"""Simple debit/credit note entry."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.accounting_note_entry import AccountingNoteEntryService
from anaj_erp.database import DatabaseManager


def test_debit_and_credit_note_roundtrip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "notes")
    databases.initialize()
    company = databases.create_company("Notes Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    party_ac = accounting.create_account("Party Ledger", "party")
    expense_ac = accounting.create_account("Misc Expense", "expense")
    income_ac = accounting.create_account("Misc Income", "income")
    party = accounting.create_party("Note Party", "customer", account_id=party_ac["account_id"])

    debit = AccountingNoteEntryService(databases, company_id, "debit_note")
    saved_debit = debit.save_note_entry(
        year_id,
        {
            "note_date": "2026-10-27",
            "note_no": "DN-1",
            "party_id": party["party_id"],
            "reference_1": "Ref-A",
            "lines": [
                {
                    "account_id": expense_ac["account_id"],
                    "account_name": "Misc Expense",
                    "particulars": "Charge back",
                    "amount": "1000",
                }
            ],
        },
    )
    assert saved_debit["note_no"] == "DN-1"
    assert saved_debit["reference_1"] == "Ref-A"

    loaded = debit.get_note_entry(year_id, note_date="2026-10-27", note_no="DN-1")
    assert loaded["document_id"] == saved_debit["document_id"]

    credit = AccountingNoteEntryService(databases, company_id, "credit_note")
    saved_credit = credit.save_note_entry(
        year_id,
        {
            "note_date": "2026-10-27",
            "note_no": "CN-1",
            "party_id": party["party_id"],
            "lines": [
                {
                    "account_id": income_ac["account_id"],
                    "account_name": "Misc Income",
                    "particulars": "Allowance",
                    "amount": "500",
                }
            ],
        },
    )
    assert saved_credit["note_no"] == "CN-1"
    assert party_ac["account_id"]
    assert expense_ac["account_id"]
    assert income_ac["account_id"]
