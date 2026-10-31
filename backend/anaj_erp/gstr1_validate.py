"""Validate GSTR-1 JSON before GSTN upload."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from .errors import ValidationError

GSTIN_RE = re.compile(
    r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$"
)
FP_RE = re.compile(r"^(0[1-9]|1[0-2])\d{4}$")
IDT_RE = re.compile(r"^(0[1-9]|[12][0-9]|3[01])-(0[1-9]|1[0-2])-(19|20)\d{2}$")
OFFLINE_VERSIONS = frozenset({"GST3.0.4", "GST3.1.0", "GST3.1.4"})


def _rupees(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def validate_gstin(gstin: str, *, field: str = "gstin") -> None:
    clean = str(gstin or "").strip().upper()
    if not GSTIN_RE.match(clean):
        raise ValidationError(f"Invalid GSTIN format for {field}")


def validate_fp(fp: str) -> None:
    clean = str(fp or "").strip()
    if not FP_RE.match(clean):
        raise ValidationError("Invalid financial period (fp); use MMYYYY")


def validate_gstr1_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Run GSTN-oriented checks; return summary or raise ValidationError."""
    errors: list[str] = []
    gstin = str(payload.get("gstin") or "").strip().upper()
    if gstin:
        try:
            validate_gstin(gstin)
        except ValidationError as exc:
            errors.append(str(exc))
    else:
        errors.append("Missing filer gstin")
    fp = str(payload.get("fp") or "")
    try:
        validate_fp(fp)
    except ValidationError as exc:
        errors.append(str(exc))

    for party in payload.get("b2b") or []:
        ctin = str(party.get("ctin") or "").upper()
        try:
            validate_gstin(ctin, field="b2b.ctin")
        except ValidationError as exc:
            errors.append(str(exc))
        for inv in party.get("inv") or []:
            if str(inv.get("rchrg") or "N") not in {"Y", "N"}:
                errors.append(f"Invalid rchrg on invoice {inv.get('inum')}")
            if str(inv.get("inv_typ") or "R") not in {"R", "SEWP", "SEWOP", "DE", "CBW"}:
                errors.append(f"Invalid inv_typ on invoice {inv.get('inum')}")

    hsn_rows = (payload.get("hsn") or {}).get("data") or []
    hsn_taxable = sum(_rupees(float(row.get("txval") or 0)) for row in hsn_rows)
    hsn_tax = sum(
        _rupees(float(row.get("iamt") or 0))
        + _rupees(float(row.get("camt") or 0))
        + _rupees(float(row.get("samt") or 0))
        + _rupees(float(row.get("csamt") or 0))
        for row in hsn_rows
    )

    outward_taxable = Decimal("0")
    for party in payload.get("b2b") or []:
        for inv in party.get("inv") or []:
            for item in inv.get("itms") or []:
                det = item.get("itm_det") or {}
                outward_taxable += _rupees(float(det.get("txval") or 0))
    for state in payload.get("b2cl") or []:
        for inv in state.get("inv") or []:
            for item in inv.get("itms") or []:
                det = item.get("itm_det") or {}
                outward_taxable += _rupees(float(det.get("txval") or 0))
    for row in payload.get("b2cs") or []:
        outward_taxable += _rupees(float(row.get("txval") or 0))

    if hsn_rows and outward_taxable > 0:
        diff = abs(hsn_taxable - outward_taxable)
        if diff > Decimal("1.00"):
            errors.append(
                "HSN summary taxable total mismatch with B2B/B2C totals "
                f"(hsn={hsn_taxable}, outward={outward_taxable})"
            )

    if errors:
        raise ValidationError("; ".join(errors))

    return {
        "ok": True,
        "hsn_taxable": float(hsn_taxable),
        "outward_taxable": float(outward_taxable),
        "hsn_tax": float(hsn_tax),
        "invoice_count": sum(len(p.get("inv") or []) for p in payload.get("b2b") or []),
    }


def validate_gstr1_offline_utility(payload: dict[str, Any]) -> dict[str, Any]:
    """Stricter checks aligned with GST Offline Utility Tool import rules."""
    try:
        base = validate_gstr1_payload(payload)
    except ValidationError as exc:
        base = {"ok": False}
        errors: list[str] = [str(exc)]
    else:
        errors = []
    version = str(payload.get("version") or "")
    if version not in OFFLINE_VERSIONS:
        errors.append(f"Unsupported GSTR-1 version for offline tool: {version}")

    def check_inv(inv: dict[str, Any], label: str) -> None:
        idt = str(inv.get("idt") or "")
        if idt and not IDT_RE.match(idt):
            errors.append(f"Invalid idt format on {label} (use DD-MM-YYYY)")
        pos = str(inv.get("pos") or "")
        if pos and (len(pos) != 2 or not pos.isdigit()):
            errors.append(f"Invalid pos on {label}")
        val = float(inv.get("val") or 0)
        if val < 0:
            errors.append(f"Negative val on {label}")
        itms = inv.get("itms") or []
        if not itms:
            errors.append(f"Missing itms on {label}")
        for item in itms:
            det = item.get("itm_det") or {}
            txval = float(det.get("txval") or 0)
            if txval < 0:
                errors.append(f"Negative txval on {label}")

    for party in payload.get("b2b") or []:
        ctin = str(party.get("ctin") or "")
        for inv in party.get("inv") or []:
            check_inv(inv, f"B2B {ctin} {inv.get('inum')}")

    for row in (payload.get("hsn") or {}).get("data") or []:
        hsn = str(row.get("hsn_sc") or "")
        if hsn and (not hsn.isdigit() or len(hsn) not in {4, 6, 8}):
            errors.append(f"Invalid hsn_sc {hsn}")
        qty = float(row.get("qty") or 0)
        if qty < 0:
            errors.append(f"Negative HSN qty for {hsn}")

    for key in ("b2b", "b2cl", "b2cs", "cdnr", "cdnur", "exp"):
        if key not in payload:
            errors.append(f"Missing required section: {key}")

    if errors:
        raise ValidationError("; ".join(errors))
    return {**base, "offline_ready": True}
