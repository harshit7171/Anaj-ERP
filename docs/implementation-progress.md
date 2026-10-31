# Anaj ERP — Implementation progress

**Overview (features, architecture, done vs left):** [project-status-and-architecture.md](project-status-and-architecture.md)  
**Box diagrams (green / yellow / red):** [architecture/visual-system-map.md](architecture/visual-system-map.md)  
**Menu → file paths:** [architecture/CODEMAP.md](architecture/CODEMAP.md)

**Database:** SQLite only (catalog + per-company DB). Default product mode is **standalone single-PC** ([standalone-mode.md](standalone-mode.md)). LAN multi-user code lives in `extra_code_Lan_Office/` (Phase 8 retained but not the default deployment).

**Canonical plan:** [erp-execution-plan.md](erp-execution-plan.md) — **Phases 0–9 implemented in code**; pilot sign-off, statutory print, and full screenshot parity are still open.

### Dev workflow (avoid rerunning the ERP every save)

Keep **Vite** (`npm run dev` → `http://127.0.0.1:5173`) and the **desktop window** (`ANAJ_ERP_DEV_URL` set) running while you code. **Frontend changes hot-reload** — no agent rerun. **Python changes:** close the desktop window and start `python -m anaj_erp.main` again only (leave Vite running). Full guide: [dev-without-rerun.md](dev-without-rerun.md). Cold start: [cursor-rerun.md](cursor-rerun.md).

---

## Phase 0 — Discovery (done)

| Item | Status | Output |
|------|--------|--------|
| Screenshot indexer | Done | `tools/` scripts, indexed assets |
| `docs/screenshot-index.json` | Done | Screen → image mapping |
| Parity matrix | Done | [reference-erp-parity-matrix.md](reference-erp-parity-matrix.md) via `tools/generate_parity_matrix.py` |
| Calculation spec | Done | [calculation-spec.md](calculation-spec.md) |
| Validation / dialog matrix | Done | [validation-dialog-matrix.md](validation-dialog-matrix.md) |

---

## Phase 1 — Shell UX (done)

| Capability | Status | Where |
|------------|--------|--------|
| Modal window pads (menu opens child window) | Done | `App.tsx`, menu hover submenus |
| Enter-to-next-field, grid Enter navigation | Done | `useFormEnterFlow`, `useGridEnterNavigation` |
| Message / validation dialogs | Done | Shared dialog components |
| Saved-state + print guards | Done | Entry screens, dense forms |
| Register PDF (no browser `window.print`) | Done | Backend PDF / `export_table` |
| Function keys F2–F12 on supported screens | Done | Per-screen handlers (F3 save/view, F4 exit, …) |
| Sky-blue workspace + right shortcut panel | Done | Global styles + `App.tsx` layout |

---

## Phase 1 — Grain ERP form audit & scaffolding (in progress)

| Item | Status | Location |
|------|--------|----------|
| Mandi monolith audit (forms, state, payloads, deps) | Done | [architecture/mandi-monolith-audit.md](architecture/mandi-monolith-audit.md) |
| `LegacyFormContainer` + `useLegacyFormKeyboard` (F2/F3/F4, Enter=Tab) | Done | `frontend/src/features/shared/` |
| Target feature folders (`form-j-entry`, `cash-book-entry`, `gate-pass-entry`, …) | Scaffold | `frontend/src/features/*/` + per-folder `README.md` |
| Router cutover from `EntryWindowImpl` | **Phase 2 partial** | **Form - J** cut over; SaleBill/CashBook/Journal still in monolith |

## Phase 2 — Component extraction & mandi state (in progress)

| Item | Status | Location |
|------|--------|----------|
| Form - J UI + state hook + router | Done | `form-j-entry/`, `useFormJEntry.ts`, `LegacyFormContainer` |
| Mandi Purchase state hook | Done | `mandi-purchase-entry/useMandiPurchase.ts` |
| Shared `calculate_document` helpers | Done | `features/shared/mandiDocumentUtils.ts` |
| `calculate_document` → `mandi.py` (Form-J charges) | Unchanged | Backend path; debounced hook same as monolith |
| DenseDocumentForm commodity audit | Done | [dense-document-form-audit.md](architecture/dense-document-form-audit.md) |
| SaleBill / CashBook / Journal extraction | Todo | Phase 2b |

## Grain Phase 3 — Statutory mandi print (done)

| Item | Status | Location |
|------|--------|----------|
| Dot-matrix `@media print` CSS (80 / 136 ch) | Done | `backend/anaj_erp/templates/mandi/mandi-statutory-print.css` |
| Form-J / Form-I HTML templates (EN + HI headers) | Done | `templates/mandi/form_*_statutory.html`, `copy_sheet_*.html` |
| Multi-copy single HTML (Farmer / Mandi / Arhtiya) | Done | `mandi_statutory_html.py` |
| ESC/POS silent raw + statutory copy labels | Done | `escpos.py`, `mandi_bills.py`, `api.print_mandi_bill` |
| Form-J one-click print (3 copies, silent) | Done | `useFormJEntry.ts` |
| HTML preview RPC | Done | `api.preview_mandi_statutory_html` |
| WebView print helper (non-silent preview) | Done | `mandi_webview_print.py` |

**Note:** Peak harvest **silent** printing uses **ESC/POS RAW** to the default dot-matrix queue; statutory HTML is for preview and laser/A4 fallback (`format: html`, `silent: false`).

## GST compliance — line tax, masters, doc_issue (done)

| Item | Location |
|------|----------|
| Line IGST/CGST/SGST/Cess on `document_line` | `database.py` migration, `documents.py`, `gst_compliance.py` |
| HSN + UQC enforcement (QTL/KGS/BAG) | `masters.save_item`, Item Entry UI |
| RCM + Sec 17(5) blocked ITC | Item metadata `blocked_itc`, expense lines `rcm_applicable` / `blocked_itc` |
| GSTR doc_issue serial summary | `gst_doc_issue` table, `gst_document_issue.py`, `list_gst_doc_issue` / `refresh_gst_doc_issue` RPC |

## HSN apportionment (GSTR-1 Table 12) — done

| Item | Location |
|------|----------|
| Freight/mandi expense apportionment by taxable value | `hsn_apportionment.py` |
| Line tax split + paise reconciliation (highest taxable line) | `reconcile_line_tax_components`, `verify_line_tax_reconciliation` |
| HSN + UQC grouping (QTL / BAG / KGS quantities) | `group_lines_by_hsn_uqc`, `build_hsn_summary_from_documents` |
| HSN Wise Summary / Table 12 UI data | `gst_report_pages.hsn_wise` |

## GSTR-1 JSON export (done)

| Item | Location |
|------|----------|
| Top-level schema (`gstin`, `fp`, `gt`, `b2b`, `b2cl`, `b2cs`, `cdnr`, `cdnur`, `exp`, `hsn`, `doc_issue`) | `gstr1_schema.py`, `gstr1_export.py` |
| B2B grouping, POS, `inv_typ`, RCM `rchrg` | `Gstr1ExportService.build` |
| B2CL (> ₹2.5L inter-state) & B2CS aggregates | same |
| CDNR / CDNUR with original invoice ref | `reference_number` + posted original lookup |
| Upload validation (GSTIN, fp, HSN totals) | `gstr1_validate.py`, `tests/test_gstr1_export.py` |
| Menu JSON export | `reports.gstr1_payload`, GST report **Form GSTR-1 JSON** |

## GSTR-2B import & matching (done)

| Item | Location |
|------|----------|
| Portal JSON parser (`b2b`, `b2ba`, `cdn`, `cdna`) | `gstr2b_ingest.py` |
| Tier 1 exact / Tier 2 fuzzy invoice / Tier 3 tax tolerance | `gstr2b_matching.py` |
| File picker + in-memory load | `api.select_gstr2b_json_file`, `load_gstr2b_json` |
| Reconcile RPC + report grid | `api.reconcile_gstr2b`, `gst_report_pages.gstr2b` |
| UI Import 2B JSON | `GstReportScreen.tsx` |
| Status buckets (Matched / Probable / In books only / In 2B only) | `classify_status_bucket`, `gstr2b_service.display_rows` |
| Grid filters + row colours + suggested actions | `GstReportScreen.tsx`, `accounts-entry.css` |

## Mock season & offline GSTR-1 (done in repo)

| Item | Location |
|------|----------|
| 520+ posted docs (wheat/paddy, bardana ITC, kachi, IGST sales, reversed vouchers) | `mock_crop_season.py`, `tools/generate_mock_season.ps1` |
| Offline-tool-oriented validation (`GST3.1.4`, required sections) | `gstr1_validate.validate_gstr1_offline_utility`, `api.validate_gstr1_offline_json` |
| Manual utility workflow | `docs/gstr1-offline-validation.md` |

**Keyboard defaults:** `LegacyFormContainer` — F2 Save, F3 View, F4 Cancel; set `saveOnF3` for lifting/mandi-style F3 Save; `saveOnF12` for old TransactionScreen parity.

---

## Phase 3 — Masters (done)

Each major master has a **feature folder** under `frontend/src/features/` and CRUD (or define-only) RPCs in `backend/anaj_erp/masters.py` unless noted.

| Menu / function | Frontend | Backend | Add/Modify blank |
|-----------------|----------|---------|------------------|
| Account Master | `account-master/` | `masters.py` (account) | Empty form + F3 save; Modify loads by code |
| City Master | `city-master/` | `masters.py` | Same pattern |
| Transport Master | `transport-master/` | `masters.py` | GSTIN fetch optional (Tools → company key) |
| Trading Master | `trading-account/` | `masters.py` | Linked item lines |
| Item Entry | `item-entry/` | `masters.py` | HSN, bag weight, variety |
| Opening / Closing Stock | `stock-entry-master/` | `masters.py` | Syncs `opening_stock` |
| Bank Master | `bank-master/` | `masters.py` | |
| IFSC Master | `ifsc-master/` | `masters.py` | |
| Expenses Master Define | `expense-master/` | `masters.py` | `lines_json` charge templates |
| I Form Expenses define | `i-form-expense-define/` | `masters.py` | |
| Cheque Print Setting | `cheque-print-setting/` | `masters.py` | Dimensions in cm |
| Standard Narration | `narration-master/` | `masters.py` | |
| Other masters (legacy bundle) | `screens/MasterForms.tsx` | `masters.py` | Being migrated to features |

**Remaining (yellow):** extract every master from `MasterForms.tsx`; split `account_master` from monolithic `masters.py` (see CODEMAP migration checklist).

---

## Phase 4 — Daily / transactions (mostly done)

| Function | UI | Backend | Depends on |
|----------|-----|---------|------------|
| Lifting Entry Add/Modify | `lifting-entry/` | `lifting_entry.py`, challan PDF | Item, parties, rate lookups |
| Kachi Purchase | `kachi-purchase/` | `kachi_purchase.py` | Item, seller party |
| Mandi Purchase Entry | `mandi-purchase-entry/` | `mandi_purchase_entry.py` | `calculations/mandi.py` |
| GST Purchase Entry | `gst-purchase-entry/` | `gst_purchase_entry.py` | Party GSTIN, items, charges |
| Invoice (daily sale) | `invoice-entry/` | `invoice_entry.py` | Party, items, tax |
| GST Debit / Credit Note | `gst-debit-note-entry/`, `gst-credit-note-entry/` | `gst_*_note_entry.py` | Party, lines, metadata JSON |
| GST Expense Voucher | `gst-expense-voucher-entry/` | `gst_expense_voucher_entry.py` | Party, expense lines |
| Accounting Debit / Credit Note | `accounting-note-entry/` | `accounting_note_entry.py` | Accounts, narration |
| Voucher Entry (Rcpt/Pymt/Contra/Journal) | `voucher-entry/` | `voucher_entry.py` | Cash/bank accounts, grid lines |
| TDS Challan Add/Modify | `tds-challan-entry/` | `tds_challan_entry.py` | Links `document_charge` |
| Bank Reconciliation | `bank-reconciliation/` | `bank_reconciliation.py` | Bank account, CSV import |
| Cash Book, Journal, Form-J, Form-I, challans, … | `legacy/EntryWindowImpl.tsx`, `DenseDocumentForm.tsx` | `documents.py`, domain-specific | **Yellow** — not all split into `features/*` |

**Posting model (all daily that save):** validate → SQLite transaction → `document` / `voucher` + lines + `document_charge` + stock movements → audit event. **Reversal**, not delete, for posted history.

---

## Phase 5 — Search + Tools (done)

| Function | UI | Backend |
|----------|-----|---------|
| Find Account | `search-screens/` | `search_screens.py` |
| Depreciation Chart | `search-screens/` | `search_screens.py` |
| Stock Adjustment Add/Modify | `search-screens/` | `search_screens.py` (`lines_json`, godown) |
| Company Letter Head Print | `search-screens/` | `search_screens.py` |
| Backup, merge, reminders, cover print, blended cost, settings, … | `screens/ToolsScreens.tsx` | `tools.py`, `modern_features.py`, `backup.py` |
| Executive dashboard | `screens/BentoDashboard.tsx` | `modern_features.py` |

See [competitive-features.md](competitive-features.md) for WhatsApp links, Clause 44, bank CSV, dashboard cards.

---

## Phase 6 — Reports 1 & 2 (mostly done)

| Function | UI | Backend |
|----------|-----|---------|
| Accounting reports (TB, ledger, cash book, day book, P&L, BS, interest, stock, registers, …) | `features/reports/LegacyReportScreen.tsx` | `report_catalog.py` → `reports.py` |
| Report key map | `app/routing/reportRegistry.ts` | Stable `report_key` strings |
| Actions | View F3, Print PDF, Excel CSV, Cancel F4 | `run_report`, `export_table` |

**Yellow:** field-by-field parity with reference ERP for every report row/column; some registers use simplified datasets.

---

## Phase 7 — GST Reports (UI done; depth yellow)

| Function | UI | Backend |
|----------|-----|---------|
| 14 GST menu screens (filters, grids, export) | `features/gst-reports/` (`gstReportSchemas.ts`, `GstReportScreen.tsx`) | `gst_report_pages.py`, `gst_report_filters.py`, `gst_reports.py` |
| Item / group pickers on month-wise reports | Same | `lookup_gst_report_items`, `lookup_gst_report_item_groups` |

**Red / yellow statutory gaps:** live GSTR-2B download, full GSTR-1 portal JSON, HSN-level tax split, POS rules — see [project-status-and-architecture.md §4.1](project-status-and-architecture.md).

---

## Phase 8 — LAN multi-user (archived for standalone)

| Item | Status | Location |
|------|--------|----------|
| FastAPI LAN server, remote client, user visibility | Implemented | `extra_code_Lan_Office/` |
| Default desktop build | Standalone | [standalone-mode.md](standalone-mode.md) |

Restore LAN only when explicitly deploying office server mode.

---

## Phase 9 — Pilot & packaging (partial)

| Item | Status |
|------|--------|
| Pilot checklist, smoke scripts | Done — [pilot-checklist.md](pilot-checklist.md) |
| Release build script | Done — `tools/build_release.ps1`, [release-build-pipeline.md](release-build-pipeline.md) |
| Accountant golden files | **Todo** — [accountant-pilot-signoff.md](accountant-pilot-signoff.md) |
| Code-signed installer | **Todo** — vendor/operator |

---

## Repository folder structure (where code lives)

```
Accblue_Software/
├── backend/anaj_erp/          # Python ERP core
│   ├── api.py                 # pywebview RPC façade (keep in sync with remoteApi.ts)
│   ├── database.py            # Schema, migrations, company DB path
│   ├── masters.py             # Master CRUD (split over time)
│   ├── documents.py           # Document posting engine
│   ├── accounting.py          # Vouchers, ledger
│   ├── calculations/          # Pure math (mandi.py)
│   ├── *_entry.py              # One module per modern entry screen
│   ├── report_catalog.py      # report_key dispatch
│   ├── reports.py             # SQL report datasets
│   ├── gst_report_pages.py    # GST menu display rows / sections
│   ├── gst_report_filters.py
│   ├── export_engine.py       # CSV/PDF table export
│   └── domains/               # Target split (in progress)
├── frontend/src/
│   ├── app/routing/           # menuRegistry, windowRouting, reportRegistry, windowCatalog
│   ├── features/              # One folder per screen family (preferred)
│   ├── features/legacy/       # EntryWindowImpl.tsx (split in progress)
│   ├── screens/               # Dashboard, Tools, MasterForms (legacy)
│   ├── styles/accounts-entry.css   # Shared entry/report “blank” layout
│   ├── Autocomplete.tsx       # search_master wrapper
│   └── api/remoteApi.ts       # Typed RPC names
├── docs/                      # Specs, progress, architecture
├── tests/                     # pytest (accounting, entries, reports, GST)
├── tools/                     # rerun_dev.ps1, parity matrix, release build
└── extra_code_Lan_Office/     # Archived LAN stack
```

### Feature folder template (new screens)

When adding a menu window, mirror an existing entry (e.g. `voucher-entry/`):

```
features/<feature-id>/
  index.ts                 # export screen
  <Feature>Screen.tsx      # UI + F-keys
  types.ts                 # form row types (optional)
  README.md                # RPC list, shortcuts
```

Wire **menu** → `menuRegistry.ts` → **router** branch in `EntryWindowImpl.tsx` (or future `resolveEntry.tsx`) → **backend** method in `api.py` + `*_entry.py`.

Details: [architecture/MODULE_LAYOUT.md](architecture/MODULE_LAYOUT.md).

---

## Blank forms, Add/Modify, and screen layout

“Blank” means the **empty Add state** and the **loaded Modify state** — same component, different initial data.

| Pattern | Behaviour | Typical keys |
|---------|-----------|--------------|
| **Add** | Menu → *Add* opens screen with defaults (today’s date, empty grid one row, zero amounts) | F3 Save, F4 Exit |
| **Modify** | Menu → *Modify* or F7 search → load by number/code → edit → save replaces draft or reverses+reposts per module rules | F7 find, F3 save |
| **Report** | No posting; filters + empty grid until View | F3 View, F4 Cancel |
| **Picker overlay** | Double-click field or *Items* button → list from `lookup_*` | Enter to select |

**Shared layout classes** (legacy ERP look):

| Class / block | Purpose |
|---------------|---------|
| `.accounts-entry-screen` | Full-page pad, padding, sky-blue frame |
| `.accounts-entry-title` | Window title centered |
| `.accounts-entry-toolbar` | Save / Delete / Print / Exit button row |
| `.accounts-entry-grid` | Line grid (no horizontal scroll — pre-approved UX rule) |
| `.picker-field` | Compact date/text inputs in filter bars |
| `.accounts-entry-status` / `.accounts-entry-error` | Green status vs red validation |
| `.accounts-picker-overlay` | Modal item/party/group picker (GST reports, entries) |

New entry screens should **reuse** `accounts-entry.css` rather than invent new spacing/fonts.

**Header metadata:** many forms store extra fields (bill no, DN reason, book no) in `document.header_metadata_json` — blank Add starts `{}`; Modify merges loaded JSON into form state.

---

## Formatting conventions (data, UI, export)

### Money and quantities

| Rule | Implementation |
|------|----------------|
| Money in DB | **Integer paise** (`*_paise` columns) — never float rupees in SQLite |
| Display in UI | Format to 2 decimals at boundary (`(paise/100).toFixed(2)` or backend `_rupees()` in reports) |
| Rates | Often stored as paise + scale; mandi qty uses `quantity_scaled` with `quantity_scale` |
| Rounding | `Decimal` + `ROUND_HALF_UP` in Python entry modules |

### Dates and financial year

| Rule | Implementation |
|------|----------------|
| Storage | ISO `YYYY-MM-DD` strings |
| FY default on reports | April 1 → today (frontend `fyStart()` helpers) |
| GST return period | Month input → `return_period` → first/last day of month in `gst_report_filters.period_from_return_month` |

### Grids and reports

| Rule | Implementation |
|------|----------------|
| Column headers | GST pages: human labels from backend `columns[]` (e.g. `Taxable Amount`) |
| Legacy reports | Often raw keys with `_` replaced by spaces in UI |
| Footer totals | Purchase & Sale Summary: `footer` object from `gst_report_pages.py` |
| Section blocks | GSTR-3B / GSTR-9: section title row + detail rows in `rows[]` |

### Print and Excel

| Output | Path |
|--------|------|
| Excel (CSV) | `export_table` with `format: "csv"`, column order = `visible_columns` |
| Print (PDF) | `export_table` with `format: "pdf"` or document-specific ReportLab in `lifting_challan_pdf.py` / invoice PDF |
| Source of truth | **Posted** documents only — PDFs do not recalculate from current master rates |

### Autocomplete display

| Entity | `search_master` label | Extra fields shown |
|--------|----------------------|-------------------|
| Party | `name` | GSTIN, address optional |
| Account | `name` | account group |
| Commodity | `name` | variety / HSN |

Screen-specific **`lookup_*`** chains (party → item → rate) return rows shaped for that form; rates may come from last posted `document_line` (rate autofill — **yellow** parity on some screens).

---

## Post-plan hardening (backlog)

- Statutory print layout sign-off (Haryana mandi)  
- Field-by-field screenshot parity for all ~147 reference screens  
- Code-signed installer distribution  
- GST statutory depth (2B import, HSN tax allocation, full GSTR-1)  
- Split `EntryWindowImpl.tsx` — `tools/split_entry_window.py`  
- Consolidate duplicate `lookup_*_parties` RPCs  

---

## Competitive / modern features (desktop)

See [competitive-features.md](competitive-features.md) — WhatsApp share links, executive dashboard, broker/item reports, bank CSV recon, Clause 44 export, tools (reminders, cover print, blended cost), fast entry, document attachments API.

---

## Migration checklist (from CODEMAP)

- [x] Routing registries under `app/routing/`
- [x] Account Master + major masters in `features/`
- [x] Calculations package `calculations/mandi.py`
- [x] Entry router in `features/legacy/EntryWindowImpl.tsx`
- [x] Voucher, TDS, bank recon, search screens, GST report shell
- [ ] Split remaining legacy Daily forms into `features/accounting/` / `features/mandi-vouchers/`
- [ ] Move `screens/*` into matching `features/*`
- [ ] Extract domain modules from `masters.py` / `api.py`

When you ship a phase item, update this file and the colour nodes in [visual-system-map.md](architecture/visual-system-map.md).
