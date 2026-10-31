"""Tests for Phase 3 mandi domain engines."""

from decimal import Decimal

import pytest

from anaj_erp.mandi_business import ApmcState
from anaj_erp.mandi_business import calculate_vyaj_interest
from anaj_erp.mandi_business import classify_rcm
from anaj_erp.mandi_business import compute_apmc_fees
from anaj_erp.mandi_business import evaluate_backdate_policy
from anaj_erp.mandi_business import merge_company_settings
from anaj_erp.mandi_business import verify_manager_pin
from anaj_erp.mandi_business import hash_manager_pin
from datetime import date


def test_apmc_haryana_grain_rates() -> None:
    lines = compute_apmc_fees(
        state=ApmcState.HARYANA.value,
        commodity_class="wheat",
        taxable_amount_paise=100_000_00,
    )
    codes = {line.code for line in lines}
    assert "MARKET_FEE" in codes
    assert "HRDF" in codes


def test_apmc_punjab_rates() -> None:
    lines = compute_apmc_fees(
        state=ApmcState.PUNJAB.value,
        commodity_class="wheat",
        taxable_amount_paise=100_000_00,
    )
    assert any(line.code == "RDF" for line in lines)


def test_rcm_freight_vs_grain() -> None:
    freight = classify_rcm(service_category="gta", is_raw_grain=False)
    grain = classify_rcm(service_category="handling", is_raw_grain=True)
    assert freight["rcm_applicable"] is True
    assert grain["rcm_applicable"] is False


def test_compound_interest_exceeds_simple() -> None:
    simple = calculate_vyaj_interest(
        principal_paise=100_000_00,
        annual_rate_percent=Decimal("12"),
        days=365,
        mode="simple",
    )
    compound = calculate_vyaj_interest(
        principal_paise=100_000_00,
        annual_rate_percent=Decimal("12"),
        days=365,
        mode="compound",
    )
    assert compound >= simple


def test_manager_pin_hash_round_trip() -> None:
    settings = merge_company_settings(
        {"manager_override_pin_hash": hash_manager_pin("1234")}
    )
    assert verify_manager_pin(settings, "1234") is True
    assert verify_manager_pin(settings, "0000") is False


def test_munim_backdate_blocked() -> None:
    settings = merge_company_settings({})
    with pytest.raises(Exception, match="Backdated"):
        evaluate_backdate_policy(
            role="munim",
            voucher_date=date(2020, 1, 1),
            today=date(2026, 4, 1),
            settings=settings,
        )
