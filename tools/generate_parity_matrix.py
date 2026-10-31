"""Refresh reference-erp-parity-matrix.md from screenshot index and code map."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "screenshot-index.json"
OUTPUT = ROOT / "docs" / "reference-erp-parity-matrix.md"

CODE_MAP = [
    ("Master", "Account / Item / City / Transport / Bank / IFSC / Narration / Expenses / Stock", "P0–P1", "MasterForms.tsx"),
    ("Daily", "Form-J, Form-I, Sale/Purchase, Kachi/Mandi/GST Purchase, Lifting", "P0–P1", "DenseDocumentForm.tsx + EntryWindow"),
    ("Entry", "Cash Book, Journal, vouchers", "P0", "EntryWindow.tsx + register PDF"),
    ("Search", "Find Account", "P1", "ToolsScreens.tsx"),
    ("Tools", "Stock adj., parameters, prefix, backup, users, merge, diagnostics", "P1", "ToolsScreens + Configuration"),
    ("Reports 1", "TB, day book, registers, stock, interest", "P1–P2", "ReportRunner + report_catalog.py"),
    ("GST Reports", "GST register, GSTR-1 JSON, GSTR-3B, HSN", "P2", "ReportRunner"),
    ("LAN", "Office server + Munim roles", "P1", "lan_server.py + remoteApi.ts"),
]


def main() -> None:
    count = 0
    if INDEX.is_file():
        payload = json.loads(INDEX.read_text(encoding="utf-8"))
        count = int(payload.get("count", 0))
    lines = [
        "# Reference ERP parity matrix",
        "",
        f"**Screenshots:** [screenshot-index.json](screenshot-index.json) ({count} files indexed).",
        "",
        "| Area | Coverage | Priority | Implementation |",
        "|------|----------|----------|----------------|",
    ]
    for area, coverage, priority, impl in CODE_MAP:
        lines.append(f"| {area} | {coverage} | {priority} | `{impl}` |")
    lines.extend(
        [
            "",
            "## Status legend",
            "",
            "- **UI** — screen reachable from menus; **Calc** — charge engine + tests; **Print** — ReportLab PDF (documents + registers)",
            "- Remaining retail gaps: statutory print layouts, full screenshot field parity, accountant golden-file sign-off (Phase 9 pilot)",
            "",
            "Regenerate: `python tools/generate_parity_matrix.py`",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
