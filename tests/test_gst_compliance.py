"""GST compliance validation and line tax allocation."""

from __future__ import annotations

import pytest

from anaj_erp.errors import ValidationError
from anaj_erp.gst_compliance import allocate_line_taxes
from anaj_erp.gst_compliance import validate_hsn
from anaj_erp.gst_compliance import validate_uqc
from anaj_erp.gst_document_issue import _split_serial


def test_validate_uqc_strict() -> None:
    assert validate_uqc("QTL") == "QTL"
    assert validate_uqc("bags") == "BAG"
    with pytest.raises(ValidationError):
        validate_uqc("LTR")


def test_validate_hsn_lengths() -> None:
    validate_hsn("1001", exempt=False)
    validate_hsn("", exempt=True)
    with pytest.raises(ValidationError):
        validate_hsn("12345", exempt=False)


def test_mixed_exempt_and_taxable_line_taxes() -> None:
    lines = [
        {"commodity_id": "wheat", "amount_paise": 100000, "metadata": {}},
        {"commodity_id": "bardana", "amount_paise": 50000, "metadata": {}},
    ]
    charges = [
        {
            "code": "CGST",
            "rate_decimal": "2.5",
            "is_tax": True,
            "final_amount_paise": 1250,
        },
        {
            "code": "SGST",
            "rate_decimal": "2.5",
            "is_tax": True,
            "final_amount_paise": 1250,
        },
    ]
    flags = {
        "wheat": {"exempted": "Yes"},
        "bardana": {"exempted": "No"},
    }
    out = allocate_line_taxes(lines, charges, flags)
    assert out[0]["cgst_paise"] == 0
    assert out[1]["cgst_paise"] + out[1]["sgst_paise"] == 2500


def test_split_serial_prefix() -> None:
    assert _split_serial("INV-1024") == ("INV-", 1024)
