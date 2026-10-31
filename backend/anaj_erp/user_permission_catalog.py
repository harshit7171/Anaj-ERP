"""Menu permission keys aligned with the React menu registry."""

from __future__ import annotations

from typing import Any

# Mirrors frontend `app/routing/menuRegistry.ts` (flat permission keys = window titles).
PERMISSION_CATALOG: list[dict[str, str]] = [
    # Master
    {"menu": "Master", "group": "Account Master", "label": "Account Add", "key": "Account Master Add"},
    {"menu": "Master", "group": "Account Master", "label": "Account Modify", "key": "Account Master Modify"},
    {"menu": "Master", "group": "Standard Narration Master", "label": "Add", "key": "Standard Narration Master Add"},
    {"menu": "Master", "group": "Standard Narration Master", "label": "Modify", "key": "Standard Narration Master Modify"},
    {"menu": "Master", "group": "City Master", "label": "Add", "key": "City Master Add"},
    {"menu": "Master", "group": "City Master", "label": "Modify", "key": "City Master Modify"},
    {"menu": "Master", "group": "Transport Master", "label": "Add", "key": "Transport Master Add"},
    {"menu": "Master", "group": "Transport Master", "label": "Modify", "key": "Transport Master Modify"},
    {"menu": "Master", "group": "Trading Master", "label": "Add", "key": "Trading Master Add"},
    {"menu": "Master", "group": "Trading Master", "label": "Modify", "key": "Trading Master Modify"},
    {"menu": "Master", "group": "", "label": "Expenses Master Define", "key": "Expenses Master Define"},
    {"menu": "Master", "group": "", "label": "I Form Expenses define", "key": "I Form Expenses define"},
    {"menu": "Master", "group": "Item Entry", "label": "Add", "key": "Item Entry Add"},
    {"menu": "Master", "group": "Item Entry", "label": "Modify", "key": "Item Entry Modify"},
    {"menu": "Master", "group": "Stock Entry", "label": "Opening Stock", "key": "Opening Stock Entry Add"},
    {"menu": "Master", "group": "Stock Entry", "label": "Closing Stock", "key": "Closing Stock Entry Modify"},
    {"menu": "Master", "group": "", "label": "Cheque Print Setting", "key": "Cheque Print Setting"},
    {"menu": "Master", "group": "Bank Master", "label": "Add", "key": "Bank Master Add"},
    {"menu": "Master", "group": "Bank Master", "label": "Modify", "key": "Bank Master Modify"},
    {"menu": "Master", "group": "IFSC Code Master", "label": "Add", "key": "IFSC Code Master Add"},
    {"menu": "Master", "group": "IFSC Code Master", "label": "Modify", "key": "IFSC Code Master Modify"},
    # Daily (subset — extend as needed)
    {"menu": "Daily", "group": "Lifting Entry", "label": "Add", "key": "Lifting Entry Add"},
    {"menu": "Daily", "group": "Lifting Entry", "label": "Modify", "key": "Lifting Entry Modify"},
    {"menu": "Daily", "group": "Kachi Purchase", "label": "Add", "key": "Kachi Purchase Add"},
    {"menu": "Daily", "group": "Kachi Purchase", "label": "Modify", "key": "Kachi Purchase Modify"},
    {"menu": "Daily", "group": "Mandi Purchase Entry", "label": "Add", "key": "Mandi Purchase Entry Add"},
    {"menu": "Daily", "group": "Mandi Purchase Entry", "label": "Modify", "key": "Mandi Purchase Entry Modify"},
    {"menu": "Daily", "group": "GST Purchase Entry", "label": "Add", "key": "GST Purchase Entry Add"},
    {"menu": "Daily", "group": "GST Purchase Entry", "label": "Modify", "key": "GST Purchase Entry Modify"},
    {"menu": "Daily", "group": "Invoice", "label": "Add", "key": "Invoice Add"},
    {"menu": "Daily", "group": "Invoice", "label": "Modify", "key": "Invoice Modify"},
    {"menu": "Daily", "group": "GST Debit Note", "label": "Add", "key": "GST Debit Note Add"},
    {"menu": "Daily", "group": "GST Debit Note", "label": "Modify", "key": "GST Debit Note Modify"},
    # GST Reports
    {"menu": "Gst Reports", "group": "", "label": "GSTR-2B Report Auto", "key": "GSTR-2B Report Auto"},
    {"menu": "Gst Reports", "group": "", "label": "Form GSTR-1(Govt)", "key": "Form GSTR-1(Govt)"},
    {"menu": "Gst Reports", "group": "", "label": "Form GSTR-3B2 Fill", "key": "Form GSTR-3B2 Fill"},
    {"menu": "Gst Reports", "group": "", "label": "HSN Wise Sale/Purchase Summary", "key": "HSN Wise Sale/Purchase Summary"},
    {"menu": "Gst Reports", "group": "", "label": "Report GSTR-9", "key": "Report GSTR-9"},
    # Tools
    {"menu": "Tools", "group": "", "label": "Backup", "key": "Configuration"},
    {"menu": "Tools", "group": "", "label": "Users", "key": "Office Users"},
    {"menu": "Tools", "group": "Settings", "label": "Company Parameters", "key": "Company Parameters"},
    {"menu": "Tools", "group": "Merging", "label": "Account Merge", "key": "Merge Parties"},
    {"menu": "Tools", "group": "", "label": "Calculator", "key": "__calculator__"},
    {"menu": "Tools", "group": "", "label": "Bank Reconciliation", "key": "Bank Reconciliation"},
    # Search / reports samples
    {"menu": "Search", "group": "", "label": "Find Account", "key": "Find Account"},
    {"menu": "Reports", "group": "Accounting Reports", "label": "Ledger", "key": "Ledger"},
    {"menu": "Reports", "group": "Accounting Reports", "label": "Trial Balance", "key": "Trial Balance"},
]


def list_permission_catalog() -> list[dict[str, Any]]:
    return [dict(row) for row in PERMISSION_CATALOG]


def normalize_permission_key(window_title: str) -> str:
    return str(window_title or "").strip()
