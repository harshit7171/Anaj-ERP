"""GSTR-2B ingestion and 3-tier matching tests."""

from __future__ import annotations

import json

from anaj_erp.gstr2b_ingest import parse_gstr2b_json
from anaj_erp.gstr2b_ingest import Gstr2bInvoiceRecord
from anaj_erp.gstr2b_matching import LocalPurchaseInvoice
from anaj_erp.gstr2b_matching import STATUS_MATCHED
from anaj_erp.gstr2b_matching import STATUS_PROBABLE
from anaj_erp.gstr2b_matching import classify_status_bucket
from anaj_erp.gstr2b_matching import match_gstr2b_to_books
from anaj_erp.gstr2b_matching import normalize_invoice_key


def test_normalize_invoice_key_strips_and_zeros() -> None:
    assert normalize_invoice_key("BARDANA/26-27/326") == normalize_invoice_key("326")
    assert normalize_invoice_key("000326") == "326"


def test_parse_gstr2b_json_b2b() -> None:
    payload = {
        "gstin": "06AABCU9603R1ZM",
        "fp": "042026",
        "b2b": [
            {
                "ctin": "07AABCS1429B1Z5",
                "inv": [
                    {
                        "inum": "BARDANA/26-27/326",
                        "idt": "15-04-2026",
                        "val": 1180.0,
                        "txval": 1000.0,
                        "iamt": 0.0,
                        "camt": 90.0,
                        "samt": 90.0,
                        "csamt": 0.0,
                    }
                ],
            }
        ],
    }
    rows = parse_gstr2b_json(json.dumps(payload))
    assert len(rows) == 1
    assert rows[0].supplier_gstin == "07AABCS1429B1Z5"
    assert rows[0].taxable_paise == 100_000


def test_tier2_fuzzy_and_tier3_tax_mismatch() -> None:
    portal = Gstr2bInvoiceRecord(
        supplier_gstin="07AABCS1429B1Z5",
        invoice_number="BARDANA/26-27/326",
        invoice_date="2026-04-15",
        invoice_value_paise=118_000,
        taxable_paise=100_000,
        igst_paise=0,
        cgst_paise=9000,
        sgst_paise=9000,
        cess_paise=0,
        source_section="b2b",
    )
    local_ok = LocalPurchaseInvoice(
        document_id="d1",
        supplier_gstin="07AABCS1429B1Z5",
        invoice_number="326",
        invoice_date="2026-04-15",
        invoice_value_paise=118_000,
        taxable_paise=100_000,
        igst_paise=0,
        cgst_paise=9000,
        sgst_paise=9000,
        cess_paise=0,
        party_name="Supplier",
    )
    matched = match_gstr2b_to_books([portal], [local_ok], tolerance_paise=100)
    assert matched["summary"]["probable_match"] == 1
    assert matched["rows"][0]["status_bucket"] == STATUS_PROBABLE
    assert matched["rows"][0]["match_tier"] == "tier2_fuzzy"
    assert (
        classify_status_bucket(
            match_status="matched",
            match_tier="tier1_exact",
            amount_ok=True,
        )
        == STATUS_MATCHED
    )

    local_bad_tax = LocalPurchaseInvoice(
        document_id="d2",
        supplier_gstin="07AABCS1429B1Z5",
        invoice_number="326",
        invoice_date="2026-04-15",
        invoice_value_paise=118_000,
        taxable_paise=100_000,
        igst_paise=0,
        cgst_paise=8000,
        sgst_paise=8000,
        cess_paise=0,
        party_name="Supplier",
    )
    mismatched = match_gstr2b_to_books([portal], [local_bad_tax], tolerance_paise=100)
    assert mismatched["summary"]["probable_match"] == 1
    assert mismatched["rows"][0]["status_bucket"] == STATUS_PROBABLE
