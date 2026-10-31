"""Module-isolated mandi formula tests (Point 16)."""

from decimal import Decimal

import pytest

from anaj_erp.mandi_calculations import apply_tare_moisture
from anaj_erp.mandi_calculations import gross_quintals_from_bags
from anaj_erp.mandi_calculations import haryana_wheat_fee_smoke
from anaj_erp.mandi_calculations import line_amount_paise
from anaj_erp.mandi_calculations import tcs_206c_1h_paise
from anaj_erp.mandi_calculations import tds_194q_paise


def test_gross_quintals_from_bags() -> None:
    gross = gross_quintals_from_bags(Decimal("10"), Decimal("50"), Decimal("25"))
    assert gross == Decimal("5.250")


def test_tare_then_moisture_sequence() -> None:
    breakdown = apply_tare_moisture(
        Decimal("100"),
        tare_quintals=Decimal("2"),
        moisture_percent=Decimal("1"),
    )
    assert breakdown.tare_quintals == Decimal("2")
    assert breakdown.moisture_quintals == Decimal("0.980")
    assert breakdown.net_quintals == Decimal("97.020")


def test_line_amount_rounding() -> None:
    amount = line_amount_paise(Decimal("97.020"), 245_000)
    assert amount == 23_769_900


def test_tcs_and_tds_helpers() -> None:
    assert tcs_206c_1h_paise(10_000_00) == 10_00
    assert tds_194q_paise(50_000_00, Decimal("0.1")) == 5_000


def test_haryana_fee_bundle_has_market_and_hrdf() -> None:
    fees = haryana_wheat_fee_smoke(100_000_00)
    assert fees["MARKET_FEE"] > 0
    assert fees["HRDF"] > 0


def test_negative_weight_rejected() -> None:
    with pytest.raises(ValueError):
        gross_quintals_from_bags(Decimal("-1"), Decimal("50"))
