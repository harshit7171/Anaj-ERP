"""Parse GSTR-2B JSON downloaded from the GST portal."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .errors import ValidationError


@dataclass(frozen=True, slots=True)
class Gstr2bInvoiceRecord:
    """One supplier invoice row from GSTR-2B."""

    supplier_gstin: str
    invoice_number: str
    invoice_date: str
    invoice_value_paise: int
    taxable_paise: int
    igst_paise: int
    cgst_paise: int
    sgst_paise: int
    cess_paise: int
    source_section: str


def _to_paise(amount: object) -> int:
    try:
        value = Decimal(str(amount or 0))
    except Exception:
        return 0
    return int((value * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _normalize_iso_date(raw: str) -> str:
    clean = str(raw or "").strip()
    if not clean:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", clean):
        return clean
    match = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", clean)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return clean


def _flatten_invoices(
    section: str,
    supplier_gstin: str,
    invoices: list[dict[str, Any]],
) -> list[Gstr2bInvoiceRecord]:
    rows: list[Gstr2bInvoiceRecord] = []
    gstin = str(supplier_gstin or "").strip().upper()
    for inv in invoices:
        if not isinstance(inv, dict):
            continue
        inum = str(inv.get("inum") or inv.get("nt_num") or inv.get("invoice_number") or "").strip()
        if not inum:
            continue
        rows.append(
            Gstr2bInvoiceRecord(
                supplier_gstin=gstin,
                invoice_number=inum,
                invoice_date=_normalize_iso_date(str(inv.get("idt") or inv.get("nt_dt") or "")),
                invoice_value_paise=_to_paise(inv.get("val")),
                taxable_paise=_to_paise(inv.get("txval") or inv.get("taxable_value")),
                igst_paise=_to_paise(inv.get("iamt")),
                cgst_paise=_to_paise(inv.get("camt")),
                sgst_paise=_to_paise(inv.get("samt")),
                cess_paise=_to_paise(inv.get("csamt")),
                source_section=section,
            )
        )
    return rows


def parse_gstr2b_json(raw: str | dict[str, Any]) -> list[Gstr2bInvoiceRecord]:
    """Load portal GSTR-2B JSON into flat invoice records."""
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError("GSTR-2B file is not valid JSON") from exc
    else:
        payload = raw
    if not isinstance(payload, dict):
        raise ValidationError("GSTR-2B JSON root must be an object")

    records: list[Gstr2bInvoiceRecord] = []
    for party in payload.get("b2b") or []:
        if not isinstance(party, dict):
            continue
        records.extend(
            _flatten_invoices("b2b", str(party.get("ctin") or ""), list(party.get("inv") or []))
        )
    for party in payload.get("b2ba") or []:
        if not isinstance(party, dict):
            continue
        records.extend(
            _flatten_invoices("b2ba", str(party.get("ctin") or ""), list(party.get("inv") or []))
        )
    for party in payload.get("cdn") or []:
        if not isinstance(party, dict):
            continue
        records.extend(
            _flatten_invoices("cdn", str(party.get("ctin") or ""), list(party.get("nt") or []))
        )
    for party in payload.get("cdna") or []:
        if not isinstance(party, dict):
            continue
        records.extend(
            _flatten_invoices("cdna", str(party.get("ctin") or ""), list(party.get("nt") or []))
        )

    # Some portal exports wrap data under "data" or ITC sections.
    data = payload.get("data")
    if isinstance(data, dict):
        for party in data.get("b2b") or []:
            if isinstance(party, dict):
                records.extend(
                    _flatten_invoices(
                        "b2b",
                        str(party.get("ctin") or ""),
                        list(party.get("inv") or []),
                    )
                )

    if not records:
        raise ValidationError("No B2B/CDN invoice rows found in GSTR-2B JSON")
    return records


def summarize_gstr2b(records: list[Gstr2bInvoiceRecord]) -> dict[str, Any]:
    suppliers = {row.supplier_gstin for row in records if row.supplier_gstin}
    return {
        "invoice_count": len(records),
        "supplier_count": len(suppliers),
        "total_taxable_paise": sum(row.taxable_paise for row in records),
        "total_tax_paise": sum(
            row.igst_paise + row.cgst_paise + row.sgst_paise + row.cess_paise for row in records
        ),
    }
