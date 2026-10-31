"""Core accounting value objects and deterministic charge calculations.

All monetary values cross the domain boundary as integer paise. Percentages and
quantities use Decimal so invoice results never depend on binary floating point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from decimal import ROUND_HALF_UP
from enum import StrEnum

from .errors import CalculationError
from .errors import ValidationError

PAISE_PER_RUPEE = 100
PERCENT_DENOMINATOR = Decimal("100")


def rupees_to_paise(value: str | Decimal) -> int:
    """Convert a rupee amount to integer paise with commercial rounding.

    Args:
        value: Decimal-compatible rupee value.

    Returns:
        Amount represented as integer paise.

    Raises:
        ValidationError: If the value is not numeric.
    """
    try:
        amount = Decimal(value)
    except Exception as exc:
        raise ValidationError("Amount must be a valid decimal number") from exc
    return int((amount * PAISE_PER_RUPEE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def paise_to_rupees(value: int) -> str:
    """Format integer paise as a two-decimal rupee value."""
    return f"{Decimal(value) / PAISE_PER_RUPEE:.2f}"


@dataclass(frozen=True, slots=True)
class FinancialYear:
    """Indian financial year running from April 1 through March 31."""

    start_year: int

    def __post_init__(self) -> None:
        """Validate a practical four-digit financial-year start."""
        if self.start_year < 2000 or self.start_year > 9998:
            raise ValidationError("Financial year start must be between 2000 and 9998")

    @property
    def starts_on(self) -> date:
        """Return April 1 of the starting calendar year."""
        return date(self.start_year, 4, 1)

    @property
    def ends_on(self) -> date:
        """Return March 31 of the following calendar year."""
        return date(self.start_year + 1, 3, 31)

    @property
    def label(self) -> str:
        """Return the display label used throughout the desktop UI."""
        return f"{self.start_year}-{self.start_year + 1}"

    def contains(self, value: date) -> bool:
        """Return whether a date belongs to this financial year."""
        return self.starts_on <= value <= self.ends_on


class ChargeBasis(StrEnum):
    """Supported bases for an effective-dated invoice charge."""

    AMOUNT = "amount"
    BAG = "bag"
    QUANTITY = "quantity"
    WEIGHT = "weight"


class ChargeMode(StrEnum):
    """How a charge rate is interpreted."""

    PERCENTAGE = "percentage"
    FIXED = "fixed"


@dataclass(frozen=True, slots=True)
class ChargeRule:
    """A deterministic percentage or fixed charge rule."""

    code: str
    label: str
    basis: ChargeBasis
    mode: ChargeMode
    rate: Decimal

    def calculate(
        self,
        *,
        amount_paise: int = 0,
        bags: Decimal = Decimal("0"),
        quantity: Decimal = Decimal("0"),
        weight: Decimal = Decimal("0"),
    ) -> int:
        """Calculate charge value as integer paise.

        Fixed rates are rupees per selected basis unit. Percentage rules are
        currently valid only for amount-based charges.

        Returns:
            Calculated charge in paise.

        Raises:
            CalculationError: If rate or basis configuration is invalid.
        """
        if self.rate < 0:
            raise CalculationError(f"Charge rate cannot be negative: {self.code}")
        if self.mode is ChargeMode.PERCENTAGE:
            if self.basis is not ChargeBasis.AMOUNT:
                raise CalculationError("Percentage charges must use amount basis")
            raw_paise = Decimal(amount_paise) * self.rate / PERCENT_DENOMINATOR
        else:
            units = {
                ChargeBasis.BAG: bags,
                ChargeBasis.QUANTITY: quantity,
                ChargeBasis.WEIGHT: weight,
                ChargeBasis.AMOUNT: Decimal("1"),
            }[self.basis]
            raw_paise = units * self.rate * PAISE_PER_RUPEE
        return int(raw_paise.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class LedgerLine:
    """One debit or credit line in a double-entry voucher."""

    account_id: str
    debit_paise: int = 0
    credit_paise: int = 0

    def __post_init__(self) -> None:
        """Reject negative or two-sided ledger lines."""
        if self.debit_paise < 0 or self.credit_paise < 0:
            raise ValidationError("Ledger amounts cannot be negative")
        if bool(self.debit_paise) == bool(self.credit_paise):
            raise ValidationError("A ledger line must contain exactly one debit or credit")


def validate_balanced(lines: list[LedgerLine]) -> None:
    """Validate that a voucher has equal debit and credit totals.

    Raises:
        ValidationError: If fewer than two lines exist or totals differ.
    """
    if len(lines) < 2:
        raise ValidationError("A voucher requires at least two ledger lines")
    debit = sum(line.debit_paise for line in lines)
    credit = sum(line.credit_paise for line in lines)
    if debit != credit:
        raise ValidationError(f"Voucher is not balanced: debit={debit}, credit={credit}")
