"""Mandi domain calculations (Phase 3/4) — server-side only.

Statutory rates, interest, APMC schedules, RCM hints, and company feature flags
live here so packaged builds do not expose arithmetic in frontend scripts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from decimal import ROUND_HALF_UP
from enum import StrEnum
from typing import Any

from .errors import ValidationError

TURNOVER_THRESHOLD_PAISE = 50_00_000 * 100  # ₹50 lakh


class IndustryMode(StrEnum):
    GRAIN = "grain"
    VEGETABLE = "vegetable"


class ArhatMode(StrEnum):
    KACHI = "kachi"
    PAKKI = "pakki"


class ApmcState(StrEnum):
    HARYANA = "haryana"
    PUNJAB = "punjab"


class InterestMode(StrEnum):
    SIMPLE = "simple"
    COMPOUND = "compound"


DEFAULT_COMPANY_SETTINGS: dict[str, Any] = {
    "industry_mode": IndustryMode.GRAIN.value,
    "arhat_mode": ArhatMode.KACHI.value,
    "apmc_state": ApmcState.HARYANA.value,
    "features": {
        "bardana_tracking": True,
        "moisture_deduction": True,
        "interest_on_advances": True,
        "sms_whatsapp_dispatch": True,
        "gate_pass_chain": True,
        "freight_allocation": True,
    },
    "automation": {
        "tds_popup_on_save": True,
        "tcs_threshold_popup": True,
        "tds_194q_popup": True,
        "rcm_freight_popup": True,
        "credit_limit_popup": True,
    },
    "rbac": {
        "munim_backdate_days": 7,
        "munim_shift_start": "09:00",
        "munim_shift_end": "20:00",
        "hide_profit_summary_for_munim": True,
        "hide_capital_accounts_for_munim": True,
        "hide_cash_vault_for_munim": True,
        "permissions": {
            "admin": {"read": "write", "reports": "write", "masters": "write"},
            "munim": {"read": "write", "reports": "read", "masters": "read"},
            "clerk": {"read": "read", "reports": "read", "masters": "none"},
            "operator": {"read": "write", "reports": "read", "masters": "none"},
            "readonly": {"read": "read", "reports": "read", "masters": "none"},
        },
    },
    "manager_override_pin_hash": "",
}


@dataclass(frozen=True, slots=True)
class ApmcFeeLine:
    code: str
    label: str
    rate_percent: Decimal
    amount_paise: int


def merge_company_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Deep-merge stored JSON with documented defaults."""
    base = json.loads(json.dumps(DEFAULT_COMPANY_SETTINGS))
    if not raw:
        return base

    def merge(into: dict[str, Any], patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(into.get(key), dict):
                merge(into[key], value)
            else:
                into[key] = value

    merge(base, raw)
    return base


def hash_manager_pin(pin: str) -> str:
    clean = pin.strip()
    if not clean:
        return ""
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def verify_manager_pin(settings: dict[str, Any], pin: str) -> bool:
    expected = str(settings.get("manager_override_pin_hash") or "")
    if not expected:
        return True
    return hash_manager_pin(pin) == expected


def industry_ui_flags(settings: dict[str, Any]) -> dict[str, bool]:
    """UI hints: which mandi fields apply for grain vs vegetable mode."""
    mode = str(settings.get("industry_mode", IndustryMode.GRAIN.value))
    grain = mode == IndustryMode.GRAIN.value
    return {
        "show_quintals": grain,
        "show_moisture": grain and bool(settings.get("features", {}).get("moisture_deduction", True)),
        "show_bardana": grain and bool(settings.get("features", {}).get("bardana_tracking", True)),
        "show_mandi_fees": grain,
        "show_hrdf_rdf": grain,
        "show_msp": grain,
        "use_crates_boxes_kg": not grain,
        "multi_month_credit_schedules": grain,
    }


def arhat_print_flags(settings: dict[str, Any]) -> dict[str, bool]:
    """Kachi vs Pakki controls commission-only vs inventory purchase print paths."""
    pakki = str(settings.get("arhat_mode", ArhatMode.KACHI.value)) == ArhatMode.PAKKI.value
    return {
        "show_commission_only_flow": not pakki,
        "show_inventory_purchase_flow": pakki,
        "assume_inventory_risk": pakki,
    }


def classify_rcm(*, service_category: str, is_raw_grain: bool) -> dict[str, Any]:
    """RCM hint for GTA/freight (taxable) vs exempt raw grain handling."""
    category = service_category.strip().lower()
    if is_raw_grain and category in {"", "handling", "storage", "grain"}:
        return {
            "rcm_applicable": False,
            "reason": "Exempt raw grain handling — RCM not suggested.",
        }
    if category in {"gta", "freight", "transport", "commercial_freight"}:
        return {
            "rcm_applicable": True,
            "reason": "Taxable GTA/commercial freight — verify reverse charge on recipient.",
        }
    return {
        "rcm_applicable": False,
        "reason": "No RCM rule matched; confirm with accountant.",
    }


def compute_apmc_fees(
    *,
    state: str,
    commodity_class: str,
    taxable_amount_paise: int,
) -> list[ApmcFeeLine]:
    """Haryana HSAMB vs Punjab PADB market fee + development cess."""
    if taxable_amount_paise < 0:
        raise ValidationError("Taxable amount cannot be negative")
    commodity = commodity_class.strip().lower()
    lines: list[ApmcFeeLine] = []
    if state == ApmcState.PUNJAB.value:
        market_rate = Decimal("3.00")
        rdf_rate = Decimal("3.00")
        market_code, rdf_code = "MARKET_FEE", "RDF"
        rdf_label = "RDF (Punjab PADB)"
    else:
        market_code, rdf_code = "MARKET_FEE", "HRDF"
        rdf_label = "HRDF (Haryana HSAMB)"
        if commodity in {"fruit", "fruits", "vegetable", "vegetables", "f&v"}:
            market_rate = Decimal("0")
            rdf_rate = Decimal("0")
        elif commodity in {"pulse", "pulses", "oilseed", "oilseeds"}:
            market_rate = Decimal("1.00")
            rdf_rate = Decimal("2.00")
        else:
            market_rate = Decimal("2.00")
            rdf_rate = Decimal("2.00")
    if market_rate > 0:
        amount = _percent_of_paise(taxable_amount_paise, market_rate)
        lines.append(
            ApmcFeeLine("MARKET_FEE", "Market Fee", market_rate, amount)
        )
    if rdf_rate > 0:
        amount = _percent_of_paise(taxable_amount_paise, rdf_rate)
        lines.append(ApmcFeeLine(rdf_code, rdf_label, rdf_rate, amount))
    return lines


def calculate_vyaj_interest(
    *,
    principal_paise: int,
    annual_rate_percent: Decimal,
    days: int,
    mode: str = InterestMode.SIMPLE.value,
    compounding_periods_per_year: int = 4,
) -> int:
    """Simple or compound interest on farmer advances (integer paise)."""
    if principal_paise < 0:
        raise ValidationError("Principal cannot be negative")
    if days < 0:
        raise ValidationError("Interest days cannot be negative")
    if annual_rate_percent < 0:
        raise ValidationError("Interest rate cannot be negative")
    if principal_paise == 0 or days == 0 or annual_rate_percent == 0:
        return 0
    rate = annual_rate_percent / Decimal("100")
    if mode == InterestMode.COMPOUND.value:
        n = max(compounding_periods_per_year, 1)
        years = Decimal(days) / Decimal("365")
        factor = (Decimal("1") + rate / Decimal(n)) ** (n * years)
        interest = Decimal(principal_paise) * (factor - Decimal("1"))
    else:
        interest = (
            Decimal(principal_paise) * rate * Decimal(days) / Decimal("365")
        )
    return int(interest.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def default_tier_expense_templates() -> list[dict[str, Any]]:
    """Seed multi-tier labour/expense rules (per bag, quintal, percent)."""
    return [
        {
            "code": "TULA",
            "label": "Tula / Weighing",
            "basis": "bag",
            "mode": "fixed",
            "rate_decimal": "4.50",
            "charge_bearer": "farmer",
            "transaction_types": ["form_j"],
        },
        {
            "code": "PALLEDARI",
            "label": "Palledari",
            "basis": "bag",
            "mode": "fixed",
            "rate_decimal": "3.50",
            "charge_bearer": "farmer",
            "transaction_types": ["form_j"],
        },
        {
            "code": "SEWING",
            "label": "Sewing / Silai",
            "basis": "bag",
            "mode": "fixed",
            "rate_decimal": "1.50",
            "charge_bearer": "farmer",
            "transaction_types": ["form_j"],
        },
        {
            "code": "GRADING",
            "label": "Grading / Cleaning",
            "basis": "quantity",
            "mode": "fixed",
            "rate_decimal": "5.00",
            "charge_bearer": "farmer",
            "transaction_types": ["form_j"],
        },
        {
            "code": "COMMISSION",
            "label": "Arhat / Commission",
            "basis": "amount",
            "mode": "percentage",
            "rate_decimal": "2.50",
            "charge_bearer": "buyer",
            "transaction_types": ["form_i_debit", "sale_invoice"],
        },
    ]


def evaluate_backdate_policy(
    *,
    role: str,
    voucher_date: date,
    today: date,
    settings: dict[str, Any],
) -> None:
    """Reject munim backdated entries outside configured window."""
    if role not in {"munim", "operator", "clerk"}:
        return
    rbac = settings.get("rbac") or {}
    max_days = int(rbac.get("munim_backdate_days", 7))
    if (today - voucher_date).days > max_days:
        raise ValidationError(
            f"Backdated entry blocked: date is more than {max_days} days old"
        )


def permission_level(settings: dict[str, Any], role: str, area: str) -> str:
    """Return none | read | write for an RBAC area."""
    matrix = (settings.get("rbac") or {}).get("permissions") or {}
    role_row = matrix.get(role) or matrix.get("munim") or {}
    level = str(role_row.get(area, "read")).lower()
    if level not in {"none", "read", "write"}:
        return "read"
    return level


def can_view_executive_tab(settings: dict[str, Any], role: str, tab: str) -> bool:
    """Hide sensitive executive tabs from munim/clerk when configured."""
    rbac = settings.get("rbac") or {}
    if role == "admin":
        return True
    if tab == "profit_summary" and rbac.get("hide_profit_summary_for_munim"):
        return role not in {"munim", "clerk", "readonly"}
    if tab == "capital" and rbac.get("hide_capital_accounts_for_munim"):
        return role not in {"munim", "clerk"}
    if tab == "cash_vault" and rbac.get("hide_cash_vault_for_munim"):
        return role not in {"munim", "clerk"}
    return True


def statutory_turnover_alerts(
    connection: Any,
    financial_year_id: str,
) -> list[dict[str, Any]]:
    """TCS 206C(1H) on sales and TDS 194Q on purchase turnover thresholds."""
    alerts: list[dict[str, Any]] = []
    sale_rows = connection.execute(
        """
        SELECT p.party_id, p.name,
            SUM(d.grand_total_paise) AS turnover_paise
        FROM document d
        JOIN party p ON p.party_id = d.party_id
        WHERE d.financial_year_id = ? AND d.status = 'posted'
            AND d.document_type IN ('sale_invoice', 'form_i_debit')
        GROUP BY p.party_id, p.name
        HAVING turnover_paise >= ?
        """,
        (financial_year_id, TURNOVER_THRESHOLD_PAISE),
    ).fetchall()
    for row in sale_rows:
        alerts.append(
            {
                "type": "tcs_206c_1h",
                "party_id": str(row["party_id"]),
                "party_name": str(row["name"]),
                "turnover_paise": int(row["turnover_paise"]),
                "message": (
                    f"TCS Sec 206C(1H): {row['name']} sale turnover crossed ₹50 lakh — "
                    "enable TCS on receipts."
                ),
            }
        )
    purchase_rows = connection.execute(
        """
        SELECT p.party_id, p.name,
            SUM(d.grand_total_paise) AS turnover_paise
        FROM document d
        JOIN party p ON p.party_id = d.party_id
        WHERE d.financial_year_id = ? AND d.status = 'posted'
            AND d.document_type IN (
                'purchase_invoice', 'mandi_purchase', 'gst_purchase', 'kachi_purchase'
            )
        GROUP BY p.party_id, p.name
        HAVING turnover_paise >= ?
        """,
        (financial_year_id, TURNOVER_THRESHOLD_PAISE),
    ).fetchall()
    for row in purchase_rows:
        alerts.append(
            {
                "type": "tds_194q",
                "party_id": str(row["party_id"]),
                "party_name": str(row["name"]),
                "turnover_paise": int(row["turnover_paise"]),
                "message": (
                    f"TDS Sec 194Q: {row['name']} purchase turnover crossed ₹50 lakh — "
                    "review TDS on trader payments."
                ),
            }
        )
    return alerts


def _percent_of_paise(amount_paise: int, rate: Decimal) -> int:
    value = (Decimal(amount_paise) * rate / Decimal("100")).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return int(value)
