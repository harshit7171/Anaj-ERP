"""Generate a full crop-season volume of posted documents for GST/load testing."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .gst_purchase_entry import GstPurchaseEntryService
from .invoice_entry import InvoiceEntryService
from .kachi_purchase import KachiPurchaseService


def generate_crop_season(
    databases: DatabaseManager,
    company_id: str,
    financial_year_id: str,
    *,
    target_count: int = 520,
) -> dict[str, Any]:
    """Post wheat/paddy season mix with mandi/GST edge cases."""
    accounting = AccountingService(databases, company_id)
    db_path = databases.company_path(company_id)

    wheat = accounting.create_commodity("WHEAT", hsn_code="1001")
    paddy = accounting.create_commodity("PADDY", hsn_code="1006")
    bardana = accounting.create_commodity("BARDANA", hsn_code="63053200")

    purchase_ac = accounting.create_account("Season Purchase", "expense")
    buyer_ac = accounting.create_account("Season Buyer", "party")
    supplier_ac = accounting.create_account("Local Supplier", "party")
    kachi_ac = accounting.create_account("Kachi Arhtiya", "party")
    buyer = accounting.create_party(
        "Interstate Mill",
        "customer",
        account_id=buyer_ac["account_id"],
        gstin="07AABCS1429B1Z5",
    )
    supplier_local = accounting.create_party(
        "Local Bardana Co",
        "supplier",
        account_id=supplier_ac["account_id"],
        gstin="06ABCDE1234F1Z5",
    )
    supplier_kachi = accounting.create_party(
        "Kachi Arhtiya",
        "supplier",
        account_id=kachi_ac["account_id"],
        gstin="06FGHIJ5678K1Z9",
    )

    gst_svc = GstPurchaseEntryService(databases, company_id)
    kachi_svc = KachiPurchaseService(databases, company_id)
    invoice_svc = InvoiceEntryService(databases, company_id)

    posted = 0
    reversed_count = 0
    start = date(2026, 4, 1)

    for index in range(target_count):
        day = start.toordinal() + (index % 180)
        entry_date = date.fromordinal(day).isoformat()
        mod = index % 10

        if mod in {0, 1, 2}:
            commodity = wheat if mod != 1 else paddy
            gst_svc.save_gst_purchase_entry(
                financial_year_id,
                {
                    "entry_date": entry_date,
                    "document_number": f"GP-SEASON-{index}",
                    "party_id": supplier_local["party_id"],
                    "bill_no": f"BARDANA/26-27/{index % 1000}",
                    "rev_charges": "N",
                    "input_claim": "Y",
                    "lines": [
                        {
                            "commodity_id": commodity["commodity_id"],
                            "item_name": str(commodity["name"]),
                            "gross_wt": "10",
                            "rate": "2200",
                            "hsn_code": str(commodity.get("hsn_code") or "1001"),
                            "cgst_pct": "2.5",
                            "sgst_pct": "2.5",
                        }
                    ],
                },
            )
        elif mod == 5:
            gst_svc.save_gst_purchase_entry(
                financial_year_id,
                {
                    "entry_date": entry_date,
                    "document_number": f"GP-RCM-{index}",
                    "party_id": supplier_local["party_id"],
                    "bill_no": f"RCM-{index}",
                    "rev_charges": "Y",
                    "input_claim": "Y",
                    "lines": [
                        {
                            "commodity_id": wheat["commodity_id"],
                            "item_name": "WHEAT",
                            "gross_wt": "8",
                            "rate": "2000",
                            "hsn_code": "1001",
                            "cgst_pct": "2.5",
                            "sgst_pct": "2.5",
                        }
                    ],
                },
            )
        elif mod == 3:
            gst_svc.save_gst_purchase_entry(
                financial_year_id,
                {
                    "entry_date": entry_date,
                    "document_number": f"GP-BARD-{index}",
                    "party_id": supplier_local["party_id"],
                    "bill_no": f"BRD-{index}",
                    "lines": [
                        {
                            "commodity_id": bardana["commodity_id"],
                            "item_name": "BARDANA",
                            "gross_wt": "5",
                            "rate": "500",
                            "hsn_code": "63053200",
                            "cgst_pct": "9",
                            "sgst_pct": "9",
                        }
                    ],
                },
            )
        elif mod == 4:
            kachi_svc.save_kachi_purchase(
                financial_year_id,
                {
                    "entry_date": entry_date,
                    "po_no": str(1000 + index),
                    "buyer_party_id": buyer["party_id"],
                    "lines": [
                        {
                            "seller_party_id": supplier_kachi["party_id"],
                            "seller_name": "Kachi Arhtiya",
                            "commodity_id": wheat["commodity_id"],
                            "bags": "20",
                            "weight": "200",
                            "rate": "2100",
                        }
                    ],
                },
            )
        else:
            invoice_svc.save_invoice_entry(
                financial_year_id,
                {
                    "entry_date": entry_date,
                    "document_number": f"SI-{index}",
                    "party_id": buyer["party_id"],
                    "bill_no": f"SI-{index}",
                    "lines": [
                        {
                            "commodity_id": wheat["commodity_id"],
                            "item_name": "WHEAT",
                            "gross_wt": "50",
                            "rate": "2400",
                            "hsn_code": "1001",
                            "cgst_pct": "0",
                            "sgst_pct": "0",
                            "igst_pct": "5",
                        }
                    ],
                },
            )
        posted += 1

        if index % 50 == 0 and index > 0:
            with databases.connect(db_path) as connection:
                connection.execute(
                    """
                    UPDATE document SET status = 'reversed'
                    WHERE document_number = ? AND financial_year_id = ?
                    """,
                    (f"GP-SEASON-{index - 1}", financial_year_id),
                )
                reversed_count += 1

    return {
        "posted": posted,
        "reversed": reversed_count,
        "purchase_account_id": purchase_ac["account_id"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate mock crop-season ERP volume")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--company-name", default="Mock Season Co")
    parser.add_argument("--count", type=int, default=520)
    args = parser.parse_args()

    databases = DatabaseManager(args.data_dir)
    databases.initialize()
    companies = databases.list_companies()
    if companies:
        company_id = str(companies[0]["company_id"])
    else:
        company_id = str(databases.create_company(args.company_name, 2026)["company_id"])
    fy_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])
    stats = generate_crop_season(databases, company_id, fy_id, target_count=args.count)
    print(stats)


if __name__ == "__main__":
    main()
