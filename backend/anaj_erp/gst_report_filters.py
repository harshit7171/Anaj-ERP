"""Shared GST report filter parsing and document type sets."""

from __future__ import annotations

import calendar
from typing import Any


def parse_gst_filters(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "commodity_id": str(params.get("commodity_id") or "").strip(),
        "item_query": str(params.get("item_query") or params.get("item_crop") or "").strip(),
        "agricultural_group": str(params.get("agricultural_group") or params.get("item_group") or "").strip(),
        "layout_mode": str(params.get("layout_mode") or params.get("show_item_month_wise") or "M").upper()[:1],
        "consolidate": _yn(params.get("consolidate"), default=False),
        "group_wise": _yn(params.get("group_wise") or params.get("show_group_wise"), default=True),
        "show_exp_detail": _yn(params.get("show_exp_detail"), default=False),
        "show_dn_cn": _yn(params.get("show_dn_cn"), default=True),
        "party_id": str(params.get("party_id") or "").strip(),
        "transaction_type": str(params.get("transaction_type") or "all").strip().lower(),
        "gstin_query": str(params.get("gstin_query") or params.get("supplier_gstin") or "").strip(),
        "b2b_b2c": str(params.get("b2b_b2c") or "all").strip().lower(),
        "itc_eligibility": str(params.get("itc_eligibility") or "all").strip().lower(),
        "hsn_code": str(params.get("hsn_code") or params.get("hsn_sac") or "").strip(),
        "transaction_side": str(params.get("transaction") or params.get("transaction_side") or "both").strip().lower(),
        "note_type": str(params.get("note_type") or "both").strip().lower(),
        "invoice_type": str(params.get("invoice_type") or "all").strip().lower(),
        "reconciliation_status": str(params.get("reconciliation_status") or "all").strip().lower(),
        "itc_action": str(params.get("itc_action") or params.get("action") or "both").strip().lower(),
        "reversal_rule": str(params.get("reversal_rule") or "all").strip().lower(),
        "itc_category": str(params.get("itc_category") or "all").strip().lower(),
    }


def period_from_return_month(params: dict[str, Any], date_from: str, date_to: str) -> tuple[str, str]:
    """Map return_period (YYYY-MM) to inclusive ISO dates when explicit dates are absent."""
    period = str(params.get("return_period") or params.get("return_month") or "").strip()
    if not period and len(date_from) >= 7 and (not date_to or date_to == date_from):
        period = date_from[:7]
    if len(period) == 7 and period[4] == "-":
        year, month = int(period[:4]), int(period[5:7])
        last = calendar.monthrange(year, month)[1]
        return f"{period}-01", f"{period}-{last:02d}"
    return date_from, date_to


def _yn(value: Any, *, default: bool) -> bool:
    text = str(value or ("Y" if default else "N")).strip().upper()
    if text in {"Y", "YES", "1", "TRUE"}:
        return True
    if text in {"N", "NO", "0", "FALSE"}:
        return False
    return default


def sale_document_types(*, include_dn_cn: bool) -> tuple[str, ...]:
    base: tuple[str, ...] = ("sale_invoice", "form_i_debit")
    if include_dn_cn:
        return base + ("gst_debit_note", "gst_credit_note")
    return base


def purchase_document_types(*, include_dn_cn: bool, include_expense: bool) -> tuple[str, ...]:
    base: tuple[str, ...] = (
        "purchase_invoice",
        "gst_purchase",
        "mandi_purchase",
        "kachi_purchase",
    )
    if include_expense:
        base = base + ("gst_expense_voucher",)
    if include_dn_cn:
        base = base + ("gst_debit_note", "gst_credit_note")
    return base
