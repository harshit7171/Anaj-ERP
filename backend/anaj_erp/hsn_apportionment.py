"""HSN apportionment — freight/mandi expenses to lines, tax split, GSTR-1 Table 12 grouping."""

from __future__ import annotations

import json
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .gst_compliance import normalize_uqc
from .gst_compliance import _yes  # noqa: PLC2701 — shared exempt helper

# Mandi / pakki charges commonly rolled into taxable value before GST.
APPORTIONABLE_CHARGE_CODES = frozenset(
    {
        "LOADING",
        "UNLOADING",
        "LABOUR",
        "FREIGHT",
        "CARTAGE",
        "HANDLING",
        "GODOWN",
        "WAREHOUSE",
        "DAMI",
        "AUCTION",
    }
)

TAX_FIELD_BY_CODE = (
    ("IGST", "igst_paise"),
    ("CGST", "cgst_paise"),
    ("SGST", "sgst_paise"),
    ("CESS", "cess_paise"),
)


def document_tax_totals(charges: list[dict[str, Any]]) -> dict[str, int]:
    """Sum voucher-level tax paise from ``document_charge`` rows."""
    totals = {"CGST": 0, "SGST": 0, "IGST": 0, "CESS": 0}
    for charge in charges:
        if not charge.get("is_tax"):
            continue
        code = str(charge.get("code") or "").upper()
        amount = int(charge.get("final_amount_paise") or 0)
        if code.startswith("IGST"):
            totals["IGST"] += amount
        elif code.startswith("CGST"):
            totals["CGST"] += amount
        elif code.startswith("SGST"):
            totals["SGST"] += amount
        elif "CESS" in code:
            totals["CESS"] += amount
    return totals


def apportionment_pool_paise(
    charges: list[dict[str, Any]],
    *,
    signed_freight_paise: int = 0,
) -> int:
    """Paise to spread across item lines (matches voucher taxable_total − subtotal)."""
    pool = int(signed_freight_paise)
    for charge in charges:
        if charge.get("is_tax"):
            continue
        if str(charge.get("code") or "").upper() == "BONUS":
            continue
        pool += int(charge.get("final_amount_paise") or 0)
    return pool


def _line_exempt(line: dict[str, Any], commodity_flags: dict[str, dict[str, Any]]) -> bool:
    flags = commodity_flags.get(str(line.get("commodity_id")), {})
    return _yes(flags.get("exempted")) or _yes((line.get("metadata") or {}).get("exempted"))


def proportional_split_paise(
    pool: int,
    weights: list[tuple[int, int]],
) -> dict[int, int]:
    """Split ``pool`` across ``(index, weight)``; remainder to highest weight index."""
    if pool == 0 or not weights:
        return {}
    total_weight = sum(weight for _, weight in weights if weight > 0)
    if total_weight <= 0:
        return {}
    shares: dict[int, int] = {}
    allocated = 0
    for index, weight in weights:
        if weight <= 0:
            shares[index] = 0
            continue
        share = int(
            (Decimal(pool) * Decimal(weight) / Decimal(total_weight)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        shares[index] = share
        allocated += share
    diff = pool - allocated
    if diff:
        anchor = max(
            ((index, weight) for index, weight in weights if weight > 0),
            key=lambda item: item[1],
        )[0]
        shares[anchor] = shares.get(anchor, 0) + diff
    return shares


def _highest_taxable_index(lines: list[dict[str, Any]]) -> int | None:
    best_index: int | None = None
    best_value = -1
    for index, line in enumerate(lines):
        taxable = int(line.get("taxable_value_paise") or line.get("amount_paise") or 0)
        if taxable > best_value:
            best_value = taxable
            best_index = index
    return best_index


def reconcile_line_tax_components(
    lines: list[dict[str, Any]],
    doc_tax: dict[str, int],
) -> list[dict[str, Any]]:
    """Force line IGST/CGST/SGST/Cess sums to match document tax header (paise-safe)."""
    if not lines:
        return lines
    anchor = _highest_taxable_index(lines)
    if anchor is None:
        return lines
    out = [dict(line) for line in lines]
    for tax_key, field in TAX_FIELD_BY_CODE:
        target = int(doc_tax.get(tax_key, 0))
        current = sum(int(row.get(field, 0)) for row in out)
        diff = target - current
        if diff:
            out[anchor][field] = max(0, int(out[anchor].get(field, 0)) + diff)
    return out


def apportion_and_allocate_line_taxes(
    lines: list[dict[str, Any]],
    charges: list[dict[str, Any]],
    commodity_flags: dict[str, dict[str, Any]],
    *,
    signed_freight_paise: int = 0,
) -> list[dict[str, Any]]:
    """Apportion freight/expenses to lines, then split document tax by taxable value."""
    doc_tax = document_tax_totals(charges)
    pool = apportionment_pool_paise(charges, signed_freight_paise=signed_freight_paise)
    taxable_weights: list[tuple[int, int]] = []
    enriched: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        row = dict(line)
        exempt = _line_exempt(row, commodity_flags)
        row["apportioned_paise"] = 0
        row["taxable_value_paise"] = int(row.get("amount_paise") or 0)
        row["igst_paise"] = 0
        row["cgst_paise"] = 0
        row["sgst_paise"] = 0
        row["cess_paise"] = 0
        if not exempt:
            taxable_weights.append((index, int(row["amount_paise"])))
        enriched.append(row)

    shares = proportional_split_paise(pool, taxable_weights)
    for index, share in shares.items():
        enriched[index]["apportioned_paise"] = share
        enriched[index]["taxable_value_paise"] = int(enriched[index]["amount_paise"]) + share
        meta = dict(enriched[index].get("metadata") or {})
        meta["apportioned_paise"] = share
        meta["taxable_value_paise"] = enriched[index]["taxable_value_paise"]
        enriched[index]["metadata"] = meta

    total_taxable = sum(int(row["taxable_value_paise"]) for row in enriched if not _line_exempt(row, commodity_flags))
    if total_taxable <= 0 or not any(doc_tax.values()):
        return enriched

    tax_weights = [
        (index, int(row["taxable_value_paise"]))
        for index, row in enumerate(enriched)
        if not _line_exempt(row, commodity_flags)
    ]
    for tax_key, field in TAX_FIELD_BY_CODE:
        target = int(doc_tax.get(tax_key, 0))
        if target == 0:
            continue
        split = proportional_split_paise(target, tax_weights)
        for index, share in split.items():
            enriched[index][field] = share

    return reconcile_line_tax_components(enriched, doc_tax)


def verify_line_tax_reconciliation(
    lines: list[dict[str, Any]],
    charges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return reconciliation status for mandi rounding checks."""
    doc_tax = document_tax_totals(charges)
    line_tax = {
        "CGST": sum(int(line.get("cgst_paise", 0)) for line in lines),
        "SGST": sum(int(line.get("sgst_paise", 0)) for line in lines),
        "IGST": sum(int(line.get("igst_paise", 0)) for line in lines),
        "CESS": sum(int(line.get("cess_paise", 0)) for line in lines),
    }
    diffs = {key: doc_tax[key] - line_tax[key] for key in doc_tax}
    return {"ok": all(value == 0 for value in diffs.values()), "document": doc_tax, "lines": line_tax, "diff_paise": diffs}


def line_quantity_for_uqc(line: dict[str, Any], uqc: str) -> Decimal:
    """Express line quantity in the UQC required for GSTR-1 Table 12."""
    code = normalize_uqc(uqc) or "QTL"
    if code == "BAG":
        bag_scale = int(line.get("bag_scale") or 0)
        bags = Decimal(int(line.get("bags_scaled") or 0))
        if bag_scale:
            return bags / (Decimal(10) ** bag_scale)
        return bags
    scale = int(line.get("quantity_scale") or 3)
    qty = Decimal(int(line.get("quantity_scaled") or 0))
    return qty / (Decimal(10) ** scale)


def group_lines_by_hsn_uqc(
    lines: list[dict[str, Any]],
    *,
    description_for: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Aggregate apportioned lines into HSN + UQC buckets (Table 12)."""
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for line in lines:
        hsn = str(line.get("hsn_code") or "").strip()
        if not hsn:
            continue
        uqc = normalize_uqc(str(line.get("uqc") or "QTL")) or "QTL"
        key = (hsn, uqc)
        bucket = buckets.setdefault(
            key,
            {
                "hsn_code": hsn,
                "uqc": uqc,
                "description": "",
                "quantity": Decimal("0"),
                "total_value_paise": 0,
                "taxable_value_paise": 0,
                "igst_paise": 0,
                "cgst_paise": 0,
                "sgst_paise": 0,
                "cess_paise": 0,
            },
        )
        if not bucket["description"]:
            name = str(line.get("commodity_name") or line.get("description") or "")
            if description_for and line.get("commodity_id"):
                name = description_for.get(str(line["commodity_id"]), name)
            bucket["description"] = name
        bucket["quantity"] += line_quantity_for_uqc(line, uqc)
        bucket["total_value_paise"] += int(line.get("amount_paise") or 0)
        bucket["taxable_value_paise"] += int(line.get("taxable_value_paise") or line.get("amount_paise") or 0)
        bucket["igst_paise"] += int(line.get("igst_paise") or 0)
        bucket["cgst_paise"] += int(line.get("cgst_paise") or 0)
        bucket["sgst_paise"] += int(line.get("sgst_paise") or 0)
        bucket["cess_paise"] += int(line.get("cess_paise") or 0)
    return sorted(buckets.values(), key=lambda row: (row["hsn_code"], row["uqc"]))


def _commodity_flags_from_rows(rows: list[Any]) -> dict[str, dict[str, Any]]:
    flags: dict[str, dict[str, Any]] = {}
    for row in rows:
        meta = json.loads(str(row["item_metadata_json"] or "{}"))
        flags[str(row["commodity_id"])] = {
            "exempted": meta.get("exempted"),
            "hsn_code": row["hsn_code"],
            "uqc": row["uqc"] or meta.get("uqc"),
        }
    return flags


def load_apportioned_documents_for_period(
    connection: Any,
    financial_year_id: str,
    date_from: str,
    date_to: str,
    document_types: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Load posted documents and run freight/expense apportionment per voucher."""
    if not document_types:
        return []
    placeholders = ",".join("?" for _ in document_types)
    headers = connection.execute(
        f"""
        SELECT document_id, freight_paise, freight_direction
        FROM document
        WHERE financial_year_id = ?
          AND status = 'posted'
          AND document_date BETWEEN ? AND ?
          AND document_type IN ({placeholders})
        ORDER BY document_date, document_number
        """,
        (financial_year_id, date_from, date_to, *document_types),
    ).fetchall()
    output: list[dict[str, Any]] = []
    for header in headers:
        document_id = str(header["document_id"])
        signed_freight = int(header["freight_paise"] or 0)
        if str(header["freight_direction"] or "add") != "add":
            signed_freight = -signed_freight
        line_rows = connection.execute(
            """
            SELECT dl.*, c.name AS commodity_name, c.hsn_code AS commodity_hsn,
                c.uqc AS commodity_uqc, c.item_metadata_json
            FROM document_line dl
            JOIN commodity c ON c.commodity_id = dl.commodity_id
            WHERE dl.document_id = ?
            ORDER BY dl.line_number
            """,
            (document_id,),
        ).fetchall()
        charge_rows = connection.execute(
            """
            SELECT code, label, final_amount_paise, is_tax, rate_decimal
            FROM document_charge
            WHERE document_id = ?
            ORDER BY line_number
            """,
            (document_id,),
        ).fetchall()
        if not line_rows:
            continue
        commodity_ids = {str(row["commodity_id"]) for row in line_rows}
        flag_rows = connection.execute(
            f"""
            SELECT commodity_id, hsn_code, uqc, item_metadata_json
            FROM commodity
            WHERE commodity_id IN ({",".join("?" for _ in commodity_ids)})
            """,
            tuple(commodity_ids),
        ).fetchall()
        commodity_flags = _commodity_flags_from_rows(flag_rows)
        lines: list[dict[str, Any]] = []
        commodity_names: dict[str, str] = {}
        for row in line_rows:
            payload = dict(row)
            payload["metadata"] = json.loads(str(payload.pop("line_metadata_json", "{}")))
            if not payload.get("hsn_code"):
                payload["hsn_code"] = payload.get("commodity_hsn")
            if not payload.get("uqc"):
                payload["uqc"] = normalize_uqc(
                    str(payload.get("commodity_uqc") or "")
                )
            commodity_names[str(payload["commodity_id"])] = str(payload.get("commodity_name") or "")
            lines.append(payload)
        charges = [dict(row) for row in charge_rows]
        apportioned = apportion_and_allocate_line_taxes(
            lines,
            charges,
            commodity_flags,
            signed_freight_paise=signed_freight,
        )
        output.append({"lines": apportioned, "commodity_names": commodity_names})
    return output


def build_hsn_summary_from_documents(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge apportioned document lines into report-ready HSN/UQC rows."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for document in documents:
        for bucket in group_lines_by_hsn_uqc(
            document["lines"],
            description_for=document.get("commodity_names"),
        ):
            key = (bucket["hsn_code"], bucket["uqc"])
            if key not in merged:
                merged[key] = {
                    **bucket,
                    "quantity": Decimal(bucket["quantity"]),
                }
                continue
            target = merged[key]
            target["quantity"] += bucket["quantity"]
            target["total_value_paise"] += bucket["total_value_paise"]
            target["taxable_value_paise"] += bucket["taxable_value_paise"]
            target["igst_paise"] += bucket["igst_paise"]
            target["cgst_paise"] += bucket["cgst_paise"]
            target["sgst_paise"] += bucket["sgst_paise"]
            target["cess_paise"] += bucket["cess_paise"]
    return sorted(merged.values(), key=lambda row: (row["hsn_code"], row["uqc"]))
