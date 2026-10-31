#!/usr/bin/env python3
"""Miracle / Aarath / Marg screen parity audit (Point 43)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENU = ROOT / "frontend" / "src" / "menuRegistry.ts"
DENSE = ROOT / "frontend" / "src" / "DenseDocumentForm.tsx"
OUTPUT = ROOT / "docs" / "parity-audit-miracle-aarath-marg.md"

LEGACY_CHECKLIST = {
    "Miracle Mandi": [
        "Form-J farmer patti deductions (tula, cleaning, advance)",
        "Form-I buyer invoice cess & commission",
        "F2–F12 keyboard shortcuts",
        "Gate pass / auction / lifting chain",
        "Munim LAN posting",
    ],
    "Aarath": [
        "Kachi vs pakki arhat modes",
        "Bardana tracking",
        "Interest on farmer advances",
        "Rokad cash book vs physical drawer",
    ],
    "Marg ERP": [
        "GST GSTR-1 / 3B exports",
        "TDS/TCS turnover alerts",
        "Multi-user RBAC",
        "Backup & restore",
    ],
}

IMPL_HINTS = {
    "Form-J": "DenseDocumentForm Form - J",
    "Form-I": "DenseDocumentForm Form - I",
    "shortcuts": "App.tsx shortcuts",
    "LAN": "extra_code_Lan_Office/backend/lan_server.py",
    "GST": "report_catalog gstr1_json",
    "cash drawer": "cash_drawer_reconciliation report",
}


def _menu_labels(source: str) -> set[str]:
    return set(re.findall(r'leaf\("([^"]+)"', source))


def main() -> None:
    menu_text = MENU.read_text(encoding="utf-8") if MENU.is_file() else ""
    dense_text = DENSE.read_text(encoding="utf-8") if DENSE.is_file() else ""
    labels = _menu_labels(menu_text)
    lines = [
        "# Miracle / Aarath / Marg parity audit",
        "",
        f"**Menu leaves detected:** {len(labels)}",
        "",
        "## Reference checklist",
        "",
    ]
    for product, items in LEGACY_CHECKLIST.items():
        lines.append(f"### {product}")
        for item in items:
            status = "partial"
            lowered = item.lower()
            if "form-j" in lowered and "Form - J" in dense_text:
                status = "implemented"
            elif "form-i" in lowered and "Form - I" in dense_text:
                status = "implemented"
            elif "shortcut" in lowered:
                status = "implemented" if "F2" in dense_text or "F4" in menu_text else "partial"
            elif "gstr" in lowered.lower():
                status = "implemented" if "GSTR-1 JSON Export" in labels else "partial"
            elif "drawer" in lowered:
                status = "implemented" if "Daily Cash Drawer Reconciliation" in labels else "missing"
            lines.append(f"- [{status}] {item}")
        lines.append("")
    lines.extend(
        [
            "## Implementation map",
            "",
            "```json",
            json.dumps(IMPL_HINTS, indent=2),
            "```",
            "",
            "Regenerate: `python tools/run_parity_audit.py`",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
