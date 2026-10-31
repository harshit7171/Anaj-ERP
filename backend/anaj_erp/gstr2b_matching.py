"""Three-tier GSTR-2B vs books reconciliation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .gstr2b_ingest import Gstr2bInvoiceRecord

DEFAULT_TAX_TOLERANCE_PAISE = 100  # ₹1

STATUS_MATCHED = "matched"
STATUS_PROBABLE = "probable_match"
STATUS_IN_BOOKS_NOT_2B = "in_books_not_in_2b"
STATUS_IN_2B_NOT_BOOKS = "in_2b_not_in_books"

STATUS_LABELS = {
    STATUS_MATCHED: "Matched",
    STATUS_PROBABLE: "Probable Match",
    STATUS_IN_BOOKS_NOT_2B: "In Books, Not in 2B",
    STATUS_IN_2B_NOT_BOOKS: "In 2B, Not in Books",
}


def classify_status_bucket(
    *,
    match_status: str,
    match_tier: str,
    amount_ok: bool,
) -> str:
    """Map reconciliation row to UI status bucket (green/yellow/red)."""
    if match_status == "in_books_only":
        return STATUS_IN_BOOKS_NOT_2B
    if match_status == "in_2b_only":
        return STATUS_IN_2B_NOT_BOOKS
    if match_tier == "tier1_exact" and amount_ok:
        return STATUS_MATCHED
    return STATUS_PROBABLE


def suggested_action(status_bucket: str, document_id: str) -> str:
    if status_bucket == STATUS_MATCHED:
        return "Accept ITC"
    if status_bucket == STATUS_PROBABLE:
        return "Review invoice / tax before claiming ITC"
    if status_bucket == STATUS_IN_BOOKS_NOT_2B:
        return "Follow up supplier GSTR-1 filing or amend books"
    if status_bucket == STATUS_IN_2B_NOT_BOOKS:
        return "Post missing purchase entry (GST purchase / mandi bill)"
    if document_id:
        return "Open purchase voucher"
    return ""


def normalize_invoice_key(value: str) -> str:
    """Strip punctuation and leading zeros; prefer last path segment (portal style)."""
    raw = str(value or "").strip()
    parts = re.split(r"[/\\-]+", raw)
    for part in reversed(parts):
        clean = re.sub(r"[^0-9A-Za-z]", "", part)
        clean = clean.lstrip("0") or "0"
        if clean:
            return clean.upper()
    clean = re.sub(r"[^0-9A-Za-z]", "", raw).lstrip("0") or "0"
    return clean.upper()


@dataclass(frozen=True, slots=True)
class LocalPurchaseInvoice:
    document_id: str
    supplier_gstin: str
    invoice_number: str
    invoice_date: str
    invoice_value_paise: int
    taxable_paise: int
    igst_paise: int
    cgst_paise: int
    sgst_paise: int
    cess_paise: int
    party_name: str


def _total_tax(row: Gstr2bInvoiceRecord | LocalPurchaseInvoice) -> int:
    return int(row.igst_paise + row.cgst_paise + row.sgst_paise + row.cess_paise)


def _exact_invoice_match(portal: Gstr2bInvoiceRecord, local: LocalPurchaseInvoice) -> bool:
    if portal.supplier_gstin != local.supplier_gstin:
        return False
    return portal.invoice_number.strip().upper() == local.invoice_number.strip().upper()


def _fuzzy_invoice_match(portal: Gstr2bInvoiceRecord, local: LocalPurchaseInvoice) -> bool:
    if portal.supplier_gstin != local.supplier_gstin:
        return False
    portal_key = normalize_invoice_key(portal.invoice_number)
    local_key = normalize_invoice_key(local.invoice_number)
    if not portal_key or not local_key:
        return False
    if portal_key == local_key:
        return True
    return portal_key.endswith(local_key) or local_key.endswith(portal_key)


def _amount_within_tolerance(
    portal: Gstr2bInvoiceRecord,
    local: LocalPurchaseInvoice,
    *,
    tolerance_paise: int,
) -> bool:
    tax_diff = abs(_total_tax(portal) - _total_tax(local))
    taxable_diff = abs(int(portal.taxable_paise) - int(local.taxable_paise))
    return tax_diff <= tolerance_paise and taxable_diff <= tolerance_paise


def match_gstr2b_to_books(
    portal_rows: list[Gstr2bInvoiceRecord],
    local_rows: list[LocalPurchaseInvoice],
    *,
    tolerance_paise: int = DEFAULT_TAX_TOLERANCE_PAISE,
) -> dict[str, Any]:
    """Tier 1 exact, tier 2 fuzzy invoice key, tier 3 tax tolerance flags."""
    unused_local = list(local_rows)
    results: list[dict[str, Any]] = []

    def pop_local(index: int) -> LocalPurchaseInvoice:
        return unused_local.pop(index)

    for portal in portal_rows:
        matched_index: int | None = None
        match_tier = ""
        for index, local in enumerate(unused_local):
            if _exact_invoice_match(portal, local):
                matched_index = index
                match_tier = "tier1_exact"
                break
        if matched_index is None:
            for index, local in enumerate(unused_local):
                if _fuzzy_invoice_match(portal, local):
                    matched_index = index
                    match_tier = "tier2_fuzzy"
                    break
        if matched_index is None:
            bucket = STATUS_IN_2B_NOT_BOOKS
            results.append(
                {
                    "status_bucket": bucket,
                    "match_status": "in_2b_only",
                    "match_tier": "",
                    "supplier_gstin": portal.supplier_gstin,
                    "portal_invoice_no": portal.invoice_number,
                    "books_invoice_no": "",
                    "portal_invoice_date": portal.invoice_date,
                    "books_invoice_date": "",
                    "party_name": "",
                    "portal_taxable": portal.taxable_paise,
                    "books_taxable": 0,
                    "portal_tax": _total_tax(portal),
                    "books_tax": 0,
                    "tax_diff_paise": _total_tax(portal),
                    "amount_ok": False,
                    "document_id": "",
                }
            )
            continue

        local = pop_local(matched_index)
        tax_diff = abs(_total_tax(portal) - _total_tax(local))
        amount_ok = _amount_within_tolerance(portal, local, tolerance_paise=tolerance_paise)
        status = "matched" if amount_ok else "amount_mismatch"
        bucket = classify_status_bucket(
            match_status=status,
            match_tier=match_tier,
            amount_ok=amount_ok,
        )
        results.append(
            {
                "status_bucket": bucket,
                "match_status": status,
                "match_tier": match_tier,
                "supplier_gstin": portal.supplier_gstin,
                "portal_invoice_no": portal.invoice_number,
                "books_invoice_no": local.invoice_number,
                "portal_invoice_date": portal.invoice_date,
                "books_invoice_date": local.invoice_date,
                "party_name": local.party_name,
                "portal_taxable": portal.taxable_paise,
                "books_taxable": local.taxable_paise,
                "portal_tax": _total_tax(portal),
                "books_tax": _total_tax(local),
                "tax_diff_paise": tax_diff,
                "amount_ok": amount_ok,
                "document_id": local.document_id,
            }
        )

    for local in unused_local:
        bucket = STATUS_IN_BOOKS_NOT_2B
        results.append(
            {
                "status_bucket": bucket,
                "match_status": "in_books_only",
                "match_tier": "",
                "supplier_gstin": local.supplier_gstin,
                "portal_invoice_no": "",
                "books_invoice_no": local.invoice_number,
                "portal_invoice_date": "",
                "books_invoice_date": local.invoice_date,
                "party_name": local.party_name,
                "portal_taxable": 0,
                "books_taxable": local.taxable_paise,
                "portal_tax": 0,
                "books_tax": _total_tax(local),
                "tax_diff_paise": _total_tax(local),
                "amount_ok": False,
                "document_id": local.document_id,
            }
        )

    summary = {
        "matched": sum(1 for row in results if row.get("status_bucket") == STATUS_MATCHED),
        "probable_match": sum(1 for row in results if row.get("status_bucket") == STATUS_PROBABLE),
        "in_books_not_in_2b": sum(
            1 for row in results if row.get("status_bucket") == STATUS_IN_BOOKS_NOT_2B
        ),
        "in_2b_not_in_books": sum(
            1 for row in results if row.get("status_bucket") == STATUS_IN_2B_NOT_BOOKS
        ),
        "tolerance_paise": tolerance_paise,
    }
    return {"rows": results, "summary": summary}
