"""GST credit note entry backend."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.gst_credit_note_entry import GstCreditNoteEntryService
from anaj_erp.invoice_entry import InvoiceEntryService


def test_gst_credit_note_save_and_find(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "gcn")
    databases.initialize()
    company = databases.create_company("GCN Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    accounting.create_account("Sales", "income")
    party_account = accounting.create_account("Customer", "party")
    party = accounting.create_party(
        "GCN Customer",
        "customer",
        account_id=party_account["account_id"],
    )
    commodity = accounting.create_commodity("MUSTARD", hsn_code="1207")

    invoice = InvoiceEntryService(databases, company_id)
    invoice.save_invoice_entry(
        year_id,
        {
            "entry_date": "2026-10-27",
            "book_no": "S-REF-2",
            "party_id": party["party_id"],
            "lines": [
                {
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "MUSTARD",
                    "qty": "4",
                    "rate": "2200",
                }
            ],
        },
    )

    service = GstCreditNoteEntryService(databases, company_id)
    saved = service.save_gst_credit_note_entry(
        year_id,
        {
            "entry_date": "2026-10-27",
            "c_note_no": "GCN-TEST-1",
            "party_id": party["party_id"],
            "pur_sale": "S",
            "input_claim_dt": "2026-10-28",
            "lines": [
                {
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "MUSTARD",
                    "qty": "1",
                    "rate": "2200",
                    "cgst_pct": "2.5",
                    "sgst_pct": "2.5",
                }
            ],
        },
    )
    assert saved["c_note_no"] == "GCN-TEST-1"
    assert saved["input_claim_dt"] == "2026-10-28"

    loaded = service.get_gst_credit_note_entry(
        year_id,
        entry_date="2026-10-27",
        party_id=party["party_id"],
        c_note_no="GCN-TEST-1",
    )
    assert loaded["document_id"] == saved["document_id"]
