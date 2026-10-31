"""HSN apportionment and GSTR-1 Table 12 aggregation."""

from __future__ import annotations

from anaj_erp.hsn_apportionment import apportion_and_allocate_line_taxes
from anaj_erp.hsn_apportionment import apportionment_pool_paise
from anaj_erp.hsn_apportionment import build_hsn_summary_from_documents
from anaj_erp.hsn_apportionment import group_lines_by_hsn_uqc
from anaj_erp.hsn_apportionment import verify_line_tax_reconciliation


def test_freight_apportioned_by_taxable_value() -> None:
    lines = [
        {
            "commodity_id": "w1",
            "amount_paise": 100_000,
            "hsn_code": "1001",
            "uqc": "QTL",
            "quantity_scaled": 100_000,
            "quantity_scale": 3,
            "bags_scaled": 0,
            "metadata": {},
        },
        {
            "commodity_id": "w2",
            "amount_paise": 50_000,
            "hsn_code": "1001",
            "uqc": "QTL",
            "quantity_scaled": 50_000,
            "quantity_scale": 3,
            "bags_scaled": 0,
            "metadata": {},
        },
    ]
    charges = [
        {"code": "LOADING", "is_tax": False, "final_amount_paise": 0},
        {"code": "CGST", "is_tax": True, "final_amount_paise": 3825, "rate_decimal": "2.5"},
        {"code": "SGST", "is_tax": True, "final_amount_paise": 3825, "rate_decimal": "2.5"},
    ]
    flags = {"w1": {"exempted": "No"}, "w2": {"exempted": "No"}}
    pool = apportionment_pool_paise(charges, signed_freight_paise=3000)
    assert pool == 3000
    out = apportion_and_allocate_line_taxes(
        lines,
        charges,
        flags,
        signed_freight_paise=3000,
    )
    assert out[0]["apportioned_paise"] == 2000
    assert out[1]["apportioned_paise"] == 1000
    assert out[0]["taxable_value_paise"] == 102_000
    check = verify_line_tax_reconciliation(out, charges)
    assert check["ok"] is True


def test_tax_remainder_on_highest_taxable_line() -> None:
    lines = [
        {"commodity_id": "a", "amount_paise": 40_000, "metadata": {}},
        {"commodity_id": "b", "amount_paise": 60_000, "metadata": {}},
    ]
    charges = [
        {"code": "CGST", "is_tax": True, "final_amount_paise": 2501, "rate_decimal": "2.5"},
        {"code": "SGST", "is_tax": True, "final_amount_paise": 2500, "rate_decimal": "2.5"},
    ]
    flags = {"a": {"exempted": "No"}, "b": {"exempted": "No"}}
    out = apportion_and_allocate_line_taxes(lines, charges, flags)
    assert verify_line_tax_reconciliation(out, charges)["ok"] is True
    assert out[1]["cgst_paise"] >= out[0]["cgst_paise"]


def test_group_by_hsn_and_uqc() -> None:
    lines = [
        {
            "hsn_code": "6305",
            "uqc": "BAG",
            "amount_paise": 10_000,
            "taxable_value_paise": 12_000,
            "bags_scaled": 50,
            "bag_scale": 0,
            "quantity_scaled": 0,
            "quantity_scale": 3,
            "cgst_paise": 100,
            "sgst_paise": 100,
            "igst_paise": 0,
            "cess_paise": 0,
            "description": "Jute Bardana",
        },
        {
            "hsn_code": "1001",
            "uqc": "QTL",
            "amount_paise": 100_000,
            "taxable_value_paise": 100_000,
            "quantity_scaled": 500_000,
            "quantity_scale": 3,
            "bags_scaled": 0,
            "bag_scale": 0,
            "cgst_paise": 0,
            "sgst_paise": 0,
            "igst_paise": 0,
            "cess_paise": 0,
            "description": "Wheat",
        },
    ]
    groups = group_lines_by_hsn_uqc(lines)
    assert len(groups) == 2
    summary = build_hsn_summary_from_documents([{"lines": lines}])
    keys = {(row["hsn_code"], row["uqc"]) for row in summary}
    assert ("6305", "BAG") in keys
    assert ("1001", "QTL") in keys
