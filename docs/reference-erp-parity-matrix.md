# Reference ERP parity matrix

**Screenshots:** [screenshot-index.json](screenshot-index.json) (147 files indexed).

| Area | Coverage | Priority | Implementation |
|------|----------|----------|----------------|
| Master | Account / Item / City / Transport / Bank / IFSC / Narration / Expenses / Stock | P0–P1 | `MasterForms.tsx` |
| Daily | Form-J, Form-I, Sale/Purchase, Kachi/Mandi/GST Purchase, Lifting | P0–P1 | `DenseDocumentForm.tsx + EntryWindow` |
| Entry | Cash Book, Journal, vouchers | P0 | `EntryWindow.tsx + register PDF` |
| Search | Find Account | P1 | `ToolsScreens.tsx` |
| Tools | Stock adj., parameters, prefix, backup, users, merge, diagnostics | P1 | `ToolsScreens + Configuration` |
| Reports 1 | TB, day book, registers, stock, interest | P1–P2 | `ReportRunner + report_catalog.py` |
| GST Reports | GST register, GSTR-1 JSON, GSTR-3B, HSN | P2 | `ReportRunner` |
| LAN | Office server + Munim roles | P1 | `lan_server.py + remoteApi.ts` |

## Status legend

- **UI** — screen reachable from menus; **Calc** — charge engine + tests; **Print** — ReportLab PDF (documents + registers)
- Remaining retail gaps: statutory print layouts, full screenshot field parity, accountant golden-file sign-off (Phase 9 pilot)

Regenerate: `python tools/generate_parity_matrix.py`
