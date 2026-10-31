"""Lifting entry save, load and challan PDF."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.database import DatabaseManager
from anaj_erp.documents import DocumentService
from anaj_erp.lifting_challan_pdf import LiftingChallanPrinter
from anaj_erp.lifting_entry import LiftingEntryService


def test_lifting_entry_save_and_print(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "lifting")
    databases.initialize()
    company = databases.create_company("Lifting Co", 2026)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    accounting = AccountingService(databases, company_id)
    purchase = accounting.create_account("Purchase", "expense")
    party_account = accounting.create_account("Purchase Party", "party")
    header_party = accounting.create_party(
        "PADDY BASMATI PURCHASE",
        "supplier",
        account_id=party_account["account_id"],
    )
    line_party = accounting.create_party("MANOJ TRADING CO", "supplier")
    commodity = accounting.create_commodity("PADDY 1121 35KG")

    documents = DocumentService(databases, company_id)
    documents.post(
        financial_year_id=year_id,
        document_type="mandi_purchase",
        document_number="MP-1",
        document_date="2026-10-18",
        party_id=header_party["party_id"],
        main_account_id=purchase["account_id"],
        party_account_id=party_account["account_id"],
        lines=[
            {
                "commodity_id": commodity["commodity_id"],
                "source_party_id": line_party["party_id"],
                "source_reference_number": "78-2026-10-18",
                "description": "PADDY 1121 35KG",
                "bags_scaled": 150,
                "bag_scale": 0,
                "packing_weight_scaled": 0,
                "loose_quantity_scaled": 0,
                "quantity_scaled": 52_500,
                "quantity_scale": 3,
                "rate_paise": 305_000,
                "rate_unit": "quintal",
                "metadata": {"ref_code": "PU1"},
            }
        ],
        header={"from_place": "KURUKHETRA"},
    )

    lifting = LiftingEntryService(databases, company_id)
    saved = lifting.save_lifting_entry(
        year_id,
        {
            "party_id": header_party["party_id"],
            "entry_date": "2026-10-22",
            "challan_no": "2",
            "dispatch_from": "KURUKHETRA",
            "vehicle_no": "PB14",
            "lines": [
                {
                    "commodity_id": commodity["commodity_id"],
                    "line_party_id": line_party["party_id"],
                    "party_name": "MANOJ TRADING CO",
                    "item_name": "PADDY 1121 35KG",
                    "unit": "Qtls",
                    "ref_code": "PU1",
                    "reference": "78-18/10/2026",
                    "qty": "150",
                    "weight": "52.500",
                    "rate": "3050",
                }
            ],
        },
    )
    assert saved["challan_no"] == "2"
    assert len(saved["lines"]) == 1
    assert saved["lines"][0]["amount"] == "160125.00"

    loaded = lifting.get_lifting_entry(
        year_id,
        entry_date="2026-10-22",
        challan_no="2",
        party_id=header_party["party_id"],
    )
    assert loaded["document_id"] == saved["document_id"]

    pdf_path = tmp_path / "challan.pdf"
    LiftingChallanPrinter(documents).create_pdf(saved["document_id"], pdf_path)
    assert pdf_path.exists()
