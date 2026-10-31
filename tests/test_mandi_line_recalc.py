"""Mandi purchase line amount/TDS sync (mirrors frontend recalcMandiLine)."""

from decimal import Decimal


def recalc_mandi_line(
    weight: str,
    rate: str,
    r_off: str,
    tds_on: str,
    tds_pct: str,
    header_tds_rate: str,
) -> tuple[str, str, str]:
    w = Decimal(weight)
    r = Decimal(rate)
    round_off = r_off.upper().startswith("Y")
    amount = w * r
    if round_off:
        amount = Decimal(int(amount.to_integral_value()))
    amount_str = f"{amount:.2f}"
    tds_on_flag = tds_on.upper().startswith("Y")
    pct = Decimal(tds_pct or header_tds_rate or "0")
    tds_base = amount if tds_on_flag else Decimal("0")
    tds = (tds_base * pct / Decimal("100")).quantize(Decimal("0.01"))
    return amount_str, amount_str if tds_on_flag else "0.00", f"{tds:.2f}"


def test_weight_rate_updates_amount_and_tds() -> None:
    amount, tds_on_amt, tds = recalc_mandi_line("10", "2500", "N", "Y", "2", "2.00")
    assert amount == "25000.00"
    assert tds_on_amt == "25000.00"
    assert tds == "500.00"


def test_round_off_yes() -> None:
    amount, _, _ = recalc_mandi_line("1.555", "100", "Y", "N", "", "2")
    assert amount == "156.00"
