"""Company print template configuration (headers, footers, QR, terms)."""

from __future__ import annotations

from typing import Any

DEFAULT_PRINT_DESIGN: dict[str, Any] = {
    "header_lines": [
        "{company_name}",
        "Commission Agent & Grain Trader",
        "Mandi License: {mandi_license_no}",
    ],
    "footer_lines": [
        "Subject to {city} jurisdiction.",
        "{custom_terms}",
    ],
    "mandi_license_no": "",
    "bank_qr_payload": "",
    "custom_terms": "Goods once sold will not be taken back.",
    "show_bank_qr": True,
    "logo_path": "",
}


def merge_print_design(raw: dict[str, Any] | None) -> dict[str, Any]:
    design = DEFAULT_PRINT_DESIGN.copy()
    if not raw:
        return design
    for key, value in raw.items():
        if key in design:
            design[key] = value
    return design


def render_template_lines(lines: list[str], context: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for line in lines:
        try:
            rendered.append(line.format(**context))
        except KeyError:
            rendered.append(line)
    return rendered
