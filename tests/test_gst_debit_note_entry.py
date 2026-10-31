"""GST debit note entry backend."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.gst_debit_note_entry import GstDebitNoteEntryService


def test_gst_debit_note_save_find_and_fill(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "gdn")
    databases.initialize()
    company = databases.create_company("GDN Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    sales = accounting.create_account("Sales", "income")
    party_account = accounting.create_account("Customer", "party")
    party = accounting.create_party(
        "GDN Customer",
        "customer",
        account_id=party_account["account_id"],
    )
    commodity = accounting.create_commodity("BARLEY", hsn_code="1003")

    service = GstDebitNoteEntryService(databases, company_id)
    from anaj_erp.invoice_entry import InvoiceEntryService

    invoice = InvoiceEntryService(databases, company_id)
    source = invoice.save_invoice_entry(
        year_id,
        {
            "entry_date": "2026-10-27",
            "book_no": "S-SRC-1",
            "party_id": party["party_id"],
            "lines": [
                {
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "BARLEY",
                    "qty": "5",
                    "rate": "1800",
                }
            ],
        },
    )

    filled = service.fill_from_source_document(
        year_id,
        party_id=party["party_id"],
        doc_no=str(source["book_no"]),
        pur_sale="S",
    )
    assert filled["lines"]

    saved = service.save_gst_debit_note_entry(
        year_id,
        {
            "entry_date": "2026-10-27",
            "d_note_no": "GDN-TEST-1",
            "party_id": party["party_id"],
            "pur_sale": "S",
            "lines": [
                {
                    "commodity_id": commodity["commodity_id"],
                    "item_name": "BARLEY",
                    "qty": "2",
                    "rate": "1800",
                    "cgst_pct": "2.5",
                    "sgst_pct": "2.5",
                }
            ],
        },
    )
    assert saved["d_note_no"] == "GDN-TEST-1"
    assert sales["account_id"]

    loaded = service.get_gst_debit_note_entry(
        year_id,
        entry_date="2026-10-27",
        party_id=party["party_id"],
        d_note_no="GDN-TEST-1",
    )
    assert loaded["document_id"] == saved["document_id"]
