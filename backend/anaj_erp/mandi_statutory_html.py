"""Statutory Form-J / Form-I HTML for APMC dot-matrix and print preview."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .print_designer import merge_print_design
from .printing import amount_in_words, money

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "mandi"

STATUTORY_COPIES: tuple[tuple[str, str, str], ...] = (
    ("farmer", "COPY 1 — FARMER / KISAN RECORD", "प्रति १ — किसान प्रति"),
    ("mandi", "COPY 2 — MANDI BOARD / APMC", "प्रति २ — मंडी बोर्ड / एपीएमसी"),
    ("arhtiya", "COPY 3 — ARHTIYA (COMMISSION AGENT)", "प्रति ३ — आढ़तिया प्रति"),
)

DEDUCTION_CODES = frozenset(
    {
        "TULA",
        "PALLEDARI",
        "SEWING",
        "GRADING",
        "MARKET_FEE",
        "HRDF",
        "MANDI",
        "APMC",
        "LOADING",
        "UNLOADING",
        "CESS",
        "MARKET",
    }
)


def _read(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _substitute(template: str, mapping: dict[str, str]) -> str:
    out = template
    for key, value in mapping.items():
        out = out.replace(f"{{{{ {key} }}}}", value)
    return out


def _line_row_form_j(line: dict[str, Any]) -> str:
    meta = line.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    bags = line.get("bags_scaled") or meta.get("bags") or 0
    qty = int(line.get("quantity_scaled") or 0) / 1000
    desc = html.escape(str(line.get("commodity_name") or line.get("description") or "—"))
    gp = html.escape(str(meta.get("gate_pass_number") or line.get("source_reference_number") or ""))
    return (
        f"<tr><td>{desc}</td><td class=\"num\">{bags}</td>"
        f"<td class=\"num\">{qty:.3f}</td>"
        f"<td class=\"num\">{money(int(line.get('rate_paise') or 0))}</td>"
        f"<td class=\"num\">{money(int(line.get('amount_paise') or 0))}</td>"
        f"<td>{gp}</td></tr>"
    )


def _line_row_form_i(line: dict[str, Any]) -> str:
    qty = int(line.get("quantity_scaled") or 0) / 1000
    desc = html.escape(str(line.get("commodity_name") or line.get("description") or "—"))
    bags = line.get("bags_scaled") or 0
    return (
        f"<tr><td>{desc}</td><td class=\"num\">{bags}</td>"
        f"<td class=\"num\">{qty:.3f}</td>"
        f"<td class=\"num\">{money(int(line.get('rate_paise') or 0))}</td>"
        f"<td class=\"num\">{money(int(line.get('amount_paise') or 0))}</td></tr>"
    )


def _deduction_rows(charges: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for charge in charges:
        code = str(charge.get("code") or "").upper()
        label = str(charge.get("label") or code)
        if code in DEDUCTION_CODES or "FEE" in code or "LOAD" in label.upper():
            rows.append(
                f"<tr><td>{html.escape(label)}</td>"
                f"<td class=\"num\">{money(int(charge.get('final_amount_paise') or 0))}</td></tr>"
            )
    if not rows:
        rows.append("<tr><td>Statutory fees (as posted)</td><td class=\"num\">—</td></tr>")
    return "\n".join(rows)


def _charge_rows_all(charges: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for charge in charges:
        label = html.escape(str(charge.get("label") or charge.get("code") or "Charge"))
        rows.append(
            f"<tr><td>{label}</td>"
            f"<td class=\"num\">{money(int(charge.get('final_amount_paise') or 0))}</td></tr>"
        )
    return "\n".join(rows) if rows else "<tr><td>—</td><td class=\"num\">—</td></tr>"


class MandiStatutoryHtmlRenderer:
    """Build multi-copy statutory HTML from posted documents."""

    def render(
        self,
        header: dict[str, Any],
        lines: list[dict[str, Any]],
        charges: list[dict[str, Any]],
        *,
        columns: int = 80,
        copy_count: int = 3,
        design: dict[str, Any] | None = None,
    ) -> str:
        doc_type = str(header.get("document_type") or "")
        if doc_type in {"form_j", "form_i_credit"}:
            return self._render_form_j(header, lines, charges, columns=columns, copy_count=copy_count, design=design)
        if doc_type in {"form_i_debit", "sale_invoice"}:
            return self._render_form_i(header, lines, charges, columns=columns, copy_count=copy_count, design=design)
        raise ValidationError(f"Statutory HTML not defined for document type: {doc_type}")

    def _render_form_j(
        self,
        header: dict[str, Any],
        lines: list[dict[str, Any]],
        charges: list[dict[str, Any]],
        *,
        columns: int,
        copy_count: int,
        design: dict[str, Any] | None,
    ) -> str:
        merged = merge_print_design(design)
        sheet_tpl = _read("copy_sheet_form_j.html")
        copies = min(max(copy_count, 1), 3)
        line_html = "\n".join(_line_row_form_j(line) for line in lines) or (
            "<tr><td colspan=\"6\">No lines</td></tr>"
        )
        gross = int(header.get("subtotal_paise") or 0)
        net = int(header.get("grand_total_paise") or 0)
        sheets: list[str] = []
        for index in range(copies):
            _key, label_en, label_hi = STATUTORY_COPIES[index]
            sheets.append(
                _substitute(
                    sheet_tpl,
                    {
                        "copy_label_en": html.escape(label_en),
                        "copy_label_hi": html.escape(label_hi),
                        "mandi_license_no": html.escape(str(merged.get("mandi_license_no") or "—")),
                        "document_date": html.escape(str(header.get("document_date") or "")),
                        "farmer_name": html.escape(str(header.get("party_name") or "—")),
                        "document_number": html.escape(str(header.get("document_number") or "")),
                        "city": html.escape(str(header.get("from_place") or header.get("to_place") or "—")),
                        "line_rows": line_html,
                        "deduction_rows": _deduction_rows(charges),
                        "gross_amount": money(gross),
                        "net_amount": money(net),
                        "amount_words": html.escape(amount_in_words(net)),
                    },
                )
            )
        wrapper = _read("form_j_statutory.html")
        col_class = "136" if columns >= 132 else "80"
        return _substitute(
            wrapper,
            {
                "document_number": html.escape(str(header.get("document_number") or "")),
                "embedded_css": _read("mandi-statutory-print.css"),
                "column_class": col_class,
                "copy_sheets": "\n".join(sheets),
            },
        )

    def _render_form_i(
        self,
        header: dict[str, Any],
        lines: list[dict[str, Any]],
        charges: list[dict[str, Any]],
        *,
        columns: int,
        copy_count: int,
        design: dict[str, Any] | None,
    ) -> str:
        sheet_tpl = _read("copy_sheet_form_i.html")
        copies = min(max(copy_count, 1), 3)
        line_html = "\n".join(_line_row_form_i(line) for line in lines)
        net = int(header.get("grand_total_paise") or 0)
        sheets: list[str] = []
        for index in range(copies):
            _key, label_en, label_hi = STATUTORY_COPIES[index]
            sheets.append(
                _substitute(
                    sheet_tpl,
                    {
                        "copy_label_en": html.escape(label_en),
                        "copy_label_hi": html.escape(label_hi),
                        "party_name": html.escape(str(header.get("party_name") or "—")),
                        "document_number": html.escape(str(header.get("document_number") or "")),
                        "document_date": html.escape(str(header.get("document_date") or "")),
                        "party_gstin": html.escape(str(header.get("party_gstin") or "—")),
                        "line_rows": line_html,
                        "charge_rows": _charge_rows_all(charges),
                        "net_amount": money(net),
                        "amount_words": html.escape(amount_in_words(net)),
                    },
                )
            )
        wrapper = _read("form_i_statutory.html")
        col_class = "136" if columns >= 132 else "80"
        return _substitute(
            wrapper,
            {
                "document_number": html.escape(str(header.get("document_number") or "")),
                "embedded_css": _read("mandi-statutory-print.css"),
                "column_class": col_class,
                "copy_sheets": "\n".join(sheets),
            },
        )

    def write_html_file(
        self,
        destination: Path,
        header: dict[str, Any],
        lines: list[dict[str, Any]],
        charges: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Path:
        destination = destination.with_suffix(".html")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.render(header, lines, charges, **kwargs), encoding="utf-8")
        return destination
