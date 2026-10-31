"""GSTR-1 JSON schema and validation tests."""

from __future__ import annotations

import pytest

from anaj_erp.errors import ValidationError
from anaj_erp.gstr1_export import B2CL_THRESHOLD_PAISE
from anaj_erp.gstr1_export import _format_idt
from anaj_erp.gstr1_export import _fp_from_date
from anaj_erp.gstr1_validate import validate_gstin
from anaj_erp.gstr1_validate import validate_gstr1_payload


VALID_GSTIN = "06AABCU9603R1ZM"


def _sample_payload() -> dict:
    return {
        "version": "GST3.1.0",
        "gstin": VALID_GSTIN,
        "fp": "042026",
        "gt": 1180.0,
        "b2b": [
            {
                "ctin": "07AABCS1429B1Z5",
                "inv": [
                    {
                        "inum": "SI-1",
                        "idt": "15-04-2026",
                        "val": 1180.0,
                        "pos": "07",
                        "rchrg": "Y",
                        "inv_typ": "R",
                        "itms": [
                            {
                                "num": 1,
                                "itm_det": {
                                    "txval": 1000.0,
                                    "rt": 18.0,
                                    "iamt": 0.0,
                                    "camt": 90.0,
                                    "samt": 90.0,
                                    "csamt": 0.0,
                                },
                            }
                        ],
                    }
                ],
            }
        ],
        "b2cl": [],
        "b2cs": [],
        "cdnr": [],
        "cdnur": [],
        "exp": [],
        "hsn": {
            "data": [
                {
                    "num": 1,
                    "hsn_sc": "1001",
                    "desc": "Wheat",
                    "uqc": "QTL",
                    "qty": 10.0,
                    "rt": 18.0,
                    "txval": 1000.0,
                    "iamt": 0.0,
                    "camt": 90.0,
                    "samt": 90.0,
                    "csamt": 0.0,
                }
            ]
        },
        "doc_issue": {"doc_det": []},
    }


def test_gstin_format_validation() -> None:
    validate_gstin(VALID_GSTIN)
    with pytest.raises(ValidationError, match="Invalid GSTIN"):
        validate_gstin("INVALID")


def test_fp_and_idt_helpers() -> None:
    assert _fp_from_date("2026-04-01") == "042026"
    assert _format_idt("2026-04-15") == "15-04-2026"


def test_gstr1_payload_passes_schema_checks() -> None:
    result = validate_gstr1_payload(_sample_payload())
    assert result["ok"] is True
    assert result["hsn_taxable"] == result["outward_taxable"]


def test_gstr1_rejects_hsn_total_mismatch() -> None:
    payload = _sample_payload()
    payload["hsn"]["data"][0]["txval"] = 500.0
    with pytest.raises(ValidationError, match="HSN summary taxable total mismatch"):
        validate_gstr1_payload(payload)


def test_b2cl_threshold_constant() -> None:
    assert B2CL_THRESHOLD_PAISE == 25_000_000
