"""GSTR-1 checks aligned with GST Offline Utility import rules."""

from __future__ import annotations

import pytest

from anaj_erp.errors import ValidationError
from anaj_erp.gstr1_validate import validate_gstr1_offline_utility


def _offline_ready_payload() -> dict:
    return {
        "version": "GST3.1.4",
        "gstin": "06AABCU9603R1ZM",
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


def test_offline_utility_accepts_gst314_payload() -> None:
    result = validate_gstr1_offline_utility(_offline_ready_payload())
    assert result.get("offline_ready") is True


def test_offline_utility_rejects_missing_sections() -> None:
    payload = _offline_ready_payload()
    del payload["cdnur"]
    with pytest.raises(ValidationError, match="Missing required section"):
        validate_gstr1_offline_utility(payload)
