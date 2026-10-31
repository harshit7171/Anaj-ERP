"""GST master validation, line-level tax allocation, and document-issue helpers."""

from __future__ import annotations

from typing import Any

from .errors import ValidationError

ALLOWED_UQC = frozenset({"QTL", "KGS", "BAG"})

UQC_ALIASES = {
    "QTL": "QTL",
    "QTL.": "QTL",
    "QUINTAL": "QTL",
    "QUINTALS": "QTL",
    "QTLs": "QTL",
    "QTl": "QTL",
    "QTLS": "QTL",
    "KGS": "KGS",
    "KG": "KGS",
    "KILOGRAM": "KGS",
    "KILOGRAMS": "KGS",
    "BAG": "BAG",
    "BAGS": "BAG",
    "NOS": "BAG",
}

HSN_LENGTHS = frozenset({4, 6, 8})


def normalize_uqc(raw: str) -> str:
    """Map legacy unit labels to GST UQC codes."""
    clean = str(raw or "").strip().upper()
    if not clean:
        return ""
    if clean in ALLOWED_UQC:
        return clean
    return UQC_ALIASES.get(clean, UQC_ALIASES.get(clean.replace(".", ""), ""))


def validate_uqc(raw: str, *, required: bool = True) -> str:
    """Enforce Anaj ERP UQC set: QTL, KGS, BAG."""
    normalized = normalize_uqc(raw)
    if not normalized:
        if required:
            raise ValidationError("UQC is required (use QTL, KGS, or BAG)")
        return ""
    if normalized not in ALLOWED_UQC:
        raise ValidationError("UQC must be QTL (Quintals), KGS (Kilograms), or BAG (Bags)")
    return normalized


def validate_hsn(hsn_code: str, *, exempt: bool = False) -> None:
    """Validate HSN/SAC length (4, 6, or 8 digits). Exempt grain may omit HSN."""
    clean = str(hsn_code or "").strip()
    if not clean:
        if exempt:
            return
        raise ValidationError("HSN/SAC code is required for taxable items")
    if not clean.isdigit():
        raise ValidationError("HSN/SAC must contain digits only")
    if len(clean) not in HSN_LENGTHS:
        raise ValidationError("HSN/SAC length must be 4, 6, or 8 digits")


def _yes(value: object) -> bool:
    return str(value or "").strip().lower() in {"y", "yes", "1", "true"}


def allocate_line_taxes(
    lines: list[dict[str, Any]],
    charges: list[dict[str, Any]],
    commodity_flags: dict[str, dict[str, Any]],
    *,
    signed_freight_paise: int = 0,
) -> list[dict[str, Any]]:
    """Apportion freight/mandi expenses and split document tax to lines (HSN engine)."""
    from .hsn_apportionment import apportion_and_allocate_line_taxes

    return apportion_and_allocate_line_taxes(
        lines,
        charges,
        commodity_flags,
        signed_freight_paise=signed_freight_paise,
    )


GST_DOC_NATURE_BY_TYPE: dict[str, str] = {
    "sale_invoice": "Invoices for outward supply",
    "invoice": "Invoices for outward supply",
    "form_i_debit": "Invoices for outward supply",
    "gst_debit_note": "Debit Note",
    "gst_credit_note": "Credit Note",
    "accounting_credit_note": "Credit Note",
    "accounting_debit_note": "Debit Note",
    "delivery_challan": "Delivery Challan in case other than by way of supply",
    "transfer_challan": "Delivery Challan in case other than by way of supply",
    "gate_pass": "Delivery Challan in case other than by way of supply",
}
