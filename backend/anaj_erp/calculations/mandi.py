"""Mandi weight and statutory calculation helpers — validate here before UI changes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from decimal import ROUND_HALF_UP

from ..mandi_business import ApmcState
from ..mandi_business import compute_apmc_fees

PAISE = Decimal("1")
KG_PER_QUINTAL = Decimal("100")


@dataclass(frozen=True, slots=True)
class WeightBreakdown:
    """Gross → tare → moisture → net billable quintals."""

    gross_quintals: Decimal
    tare_quintals: Decimal
    moisture_quintals: Decimal
    net_quintals: Decimal


def gross_quintals_from_bags(
    bags: Decimal,
    bag_weight_kg: Decimal,
    loose_kg: Decimal = Decimal("0"),
) -> Decimal:
    """Convert bag count + loose kg to gross quintals (100 kg)."""
    if bags < 0 or bag_weight_kg < 0 or loose_kg < 0:
        raise ValueError("Weights cannot be negative")
    total_kg = bags * bag_weight_kg + loose_kg
    return (total_kg / KG_PER_QUINTAL).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def apply_tare_moisture(
    gross_quintals: Decimal,
    *,
    tare_quintals: Decimal = Decimal("0"),
    moisture_percent: Decimal = Decimal("0"),
) -> WeightBreakdown:
    """Deduct tare then moisture % on remaining gross (standard mandi sequence)."""
    if gross_quintals < 0:
        raise ValueError("Gross quintals cannot be negative")
    if tare_quintals < 0 or moisture_percent < 0:
        raise ValueError("Deductions cannot be negative")
    after_tare = max(Decimal("0"), gross_quintals - tare_quintals)
    moisture_q = (after_tare * moisture_percent / Decimal("100")).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP,
    )
    net = max(Decimal("0"), after_tare - moisture_q)
    return WeightBreakdown(
        gross_quintals=gross_quintals,
        tare_quintals=tare_quintals,
        moisture_quintals=moisture_q,
        net_quintals=net,
    )


def line_amount_paise(net_quintals: Decimal, rate_paise_per_quintal: int) -> int:
    """Billable line value in paise."""
    if net_quintals < 0 or rate_paise_per_quintal < 0:
        raise ValueError("Rate and quantity must be non-negative")
    value = (net_quintals * Decimal(rate_paise_per_quintal)).quantize(
        PAISE,
        rounding=ROUND_HALF_UP,
    )
    return int(value)


def tcs_206c_1h_paise(sale_turnover_paise: int, rate_percent: Decimal = Decimal("0.1")) -> int:
    """TCS on sale consideration above threshold (rate configurable)."""
    if sale_turnover_paise <= 0:
        return 0
    return int(
        (Decimal(sale_turnover_paise) * rate_percent / Decimal("100")).quantize(
            PAISE,
            rounding=ROUND_HALF_UP,
        )
    )


def tds_194q_paise(purchase_turnover_paise: int, rate_percent: Decimal = Decimal("0.1")) -> int:
    """TDS 194Q on purchase payments (rate configurable)."""
    if purchase_turnover_paise <= 0:
        return 0
    return int(
        (Decimal(purchase_turnover_paise) * rate_percent / Decimal("100")).quantize(
            PAISE,
            rounding=ROUND_HALF_UP,
        )
    )


def mandi_fee_bundle_paise(
    state: str,
    commodity_class: str,
    taxable_amount_paise: int,
) -> dict[str, int]:
    """APMC market fee + RDF/HRDF totals keyed by fee code."""
    lines = compute_apmc_fees(
        state=state,
        commodity_class=commodity_class,
        taxable_amount_paise=taxable_amount_paise,
    )
    return {line.code: line.amount_paise for line in lines}


def haryana_wheat_fee_smoke(taxable_amount_paise: int) -> dict[str, int]:
    """Convenience wrapper for tests."""
    return mandi_fee_bundle_paise(ApmcState.HARYANA.value, "wheat", taxable_amount_paise)
