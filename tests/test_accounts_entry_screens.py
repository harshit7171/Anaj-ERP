"""Voucher Entry, TDS Challan, Bank Reconciliation."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.bank_reconciliation import BankReconciliationService
import uuid

from anaj_erp.database import utc_now
from anaj_erp.tds_challan_entry import TdsChallanEntryService
from anaj_erp.voucher_entry import VoucherEntryService


def test_voucher_entry_receipt_roundtrip(tmp_path: Path) -> None:
    from anaj_erp.database import DatabaseManager

    databases = DatabaseManager(tmp_path / "voucher")
    databases.initialize()
    company = databases.create_company("Voucher Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    cash = accounting.create_account("Cash In Hand", "cash")
    party_ac = accounting.create_account("Party Ledger", "party")
    accounting.create_party("Receipt Party", "customer", account_id=party_ac["account_id"])

    service = VoucherEntryService(databases, company_id)
    saved = service.save_voucher_entry(
        year_id,
        {
            "voucher_type": "Receipt",
            "voucher_date": "2026-10-27",
            "voucher_number": "R-1",
            "payment_mode": "Cash",
            "header_account_id": cash["account_id"],
            "lines": [
                {
                    "account_id": party_ac["account_id"],
                    "account_name": "Party Ledger",
                    "amount": "1000",
                    "narration": "On account",
                }
            ],
        },
    )
    assert saved["voucher_number"] == "R-1"
    loaded = service.get_voucher_entry(
        year_id,
        voucher_number="R-1",
        voucher_date="2026-10-27",
        voucher_type="Receipt",
    )
    assert loaded["voucher_id"] == saved["voucher_id"]
    assert len(loaded["lines"]) == 1


def test_tds_challan_links_charges(tmp_path: Path) -> None:
    from anaj_erp.database import DatabaseManager

    databases = DatabaseManager(tmp_path / "tds")
    databases.initialize()
    company = databases.create_company("TDS Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    party_ac = accounting.create_account("Vendor", "party")
    party = accounting.create_party("Vendor One", "supplier", account_id=party_ac["account_id"])
    document_id = str(uuid.uuid4())
    charge_id = str(uuid.uuid4())
    timestamp = utc_now()
    with databases.connect(databases.company_path(company_id)) as connection:
        connection.execute(
            """
            INSERT INTO document(
                document_id, financial_year_id, document_type, document_number,
                document_date, party_id, status, grand_total_paise,
                header_metadata_json, calculation_snapshot_json, created_at, updated_at
            ) VALUES (?, ?, 'gst_expense_voucher', 'GEV-TDS-1', '2026-10-20', ?, 'posted',
                1000000, '{}', '{}', ?, ?)
            """,
            (document_id, year_id, party["party_id"], timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO document_charge(
                document_charge_id, document_id, line_number, code, label, basis,
                rate_decimal, automatic_amount_paise, final_amount_paise, is_tax
            ) VALUES (?, ?, 1, 'TDS', 'TDS 2%', 'amount', '2', 20000, 20000, 1)
            """,
            (charge_id, document_id),
        )

    challan = TdsChallanEntryService(databases, company_id)
    pending = challan.list_pending_lines(year_id, "2026-10-01", "2026-10-31")
    assert any(row["document_charge_id"] == charge_id for row in pending)

    saved = challan.save_challan_entry(
        year_id,
        {
            "challan_date": "2026-10-27",
            "challan_no": "CH-100",
            "filter_date_from": "2026-10-01",
            "filter_date_to": "2026-10-31",
            "selected_charge_ids": [charge_id],
        },
    )
    assert saved["challan_no"] == "CH-100"
    assert float(saved["tds_total_amt"]) == 200.0


def test_bank_reconciliation_search(tmp_path: Path) -> None:
    from anaj_erp.database import DatabaseManager

    databases = DatabaseManager(tmp_path / "bank")
    databases.initialize()
    company = databases.create_company("Bank Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    bank = accounting.create_account("HDFC Bank", "bank")
    party_ac = accounting.create_account("Party", "party")
    accounting.create_party("P", "customer", account_id=party_ac["account_id"])

    voucher = VoucherEntryService(databases, company_id)
    voucher.save_voucher_entry(
        year_id,
        {
            "voucher_type": "Receipt",
            "voucher_date": "2026-10-15",
            "voucher_number": "BR-1",
            "payment_mode": "Bank",
            "header_account_id": bank["account_id"],
            "lines": [{"account_id": party_ac["account_id"], "amount": "500", "narration": "Chq 999"}],
        },
    )

    recon = BankReconciliationService(databases, company_id)
    rows = recon.search_lines(
        year_id,
        {
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
            "bank_name": "HDFC",
        },
    )
    assert len(rows) >= 1
