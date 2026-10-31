# CODEMAP — where to edit each screen

Use this file to **point Cursor or a developer at one folder** without scanning the whole repo.

Layout rules: [MODULE_LAYOUT.md](./MODULE_LAYOUT.md)  
Machine-readable index: `frontend/src/app/routing/windowCatalog.ts`

---

## Quick reference

| Area | Frontend | Backend |
|------|----------|---------|
| **Account Master** | `frontend/src/features/account-master/` | `backend/anaj_erp/masters.py` (`save_account_master`, `get_*`, `delete_*`) |
| **Other masters** (City, Item, Bank, …) | `frontend/src/screens/MasterForms.tsx` | `backend/anaj_erp/masters.py` |
| **Mandi calculations** (weights, TCS/TDS, fees) | — | `backend/anaj_erp/calculations/mandi.py` |
| **Menu / window titles** | `frontend/src/app/routing/menuRegistry.ts` | — |
| **Title → screen resolution** | `frontend/src/app/routing/windowRouting.ts` | — |
| **Reports catalog** | `frontend/src/app/routing/reportRegistry.ts` | `backend/anaj_erp/report_catalog.py`, `reports.py` |
| **Entry router (all windows)** | `frontend/src/features/legacy/EntryWindowImpl.tsx` | `backend/anaj_erp/api.py` |
| **Thin entry export** | `frontend/src/EntryWindow.tsx` | — |
| **Desktop API façade** | `frontend/src/api/types.ts`, `remoteApi.ts` | `backend/anaj_erp/api.py` |
| **Dense vouchers** (Kachi, GST purchase, …) | `frontend/src/DenseDocumentForm.tsx` | `backend/anaj_erp/documents.py` |
| **Lifting Entry** Add / Modify | `frontend/src/features/lifting-entry/` | `backend/anaj_erp/lifting_entry.py`, `lifting_challan_pdf.py` |
| **Kachi Purchase** Add / Modify | `frontend/src/features/kachi-purchase/` | `backend/anaj_erp/kachi_purchase.py` |
| **Mandi Purchase Entry** Add / Modify | `frontend/src/features/mandi-purchase-entry/` | `backend/anaj_erp/mandi_purchase_entry.py` |
| **GST Purchase Entry** Add / Modify | `frontend/src/features/gst-purchase-entry/` | `backend/anaj_erp/gst_purchase_entry.py` |
| **Invoice** Add / Modify (Daily) | `frontend/src/features/invoice-entry/` | `backend/anaj_erp/invoice_entry.py` |
| **GST Debit Note** Add / Modify | `frontend/src/features/gst-debit-note-entry/` | `backend/anaj_erp/gst_debit_note_entry.py` |
| **GST Credit Note** Add / Modify | `frontend/src/features/gst-credit-note-entry/` | `backend/anaj_erp/gst_credit_note_entry.py` |
| **GST Expense Voucher** Add / Modify | `frontend/src/features/gst-expense-voucher-entry/` | `backend/anaj_erp/gst_expense_voucher_entry.py` |
| **Debit Note / Credit Note** Add / Modify | `frontend/src/features/accounting-note-entry/` | `backend/anaj_erp/accounting_note_entry.py` |
| **Voucher Entry** Add / Modify | `frontend/src/features/voucher-entry/` | `backend/anaj_erp/voucher_entry.py` |
| **TDS Challan Entry** Add / Modify | `frontend/src/features/tds-challan-entry/` | `backend/anaj_erp/tds_challan_entry.py` |
| **Bank Reconciliation** | `frontend/src/features/bank-reconciliation/` | `backend/anaj_erp/bank_reconciliation.py` |
| **Reports menu (legacy UI)** | `frontend/src/features/reports/` | `backend/anaj_erp/report_catalog.py`, `reports.py` |
| **GST Reports menu (14 screens)** | `frontend/src/features/gst-reports/` (`gstReportSchemas.ts`, `GstReportScreen.tsx`) | `gst_report_pages.py`, `report_catalog.py`, `gst_report_filters.py`, `gst_reports.py` |
| **Find Account / Depreciation / Stock Adj. / Letter Head** | `frontend/src/features/search-screens/` | `backend/anaj_erp/search_screens.py` |
| **Tools** (backup, merge, …) | `frontend/src/screens/ToolsScreens.tsx` | `backend/anaj_erp/tools.py` |
| **Dashboard** | `frontend/src/screens/BentoDashboard.tsx` | `backend/anaj_erp/modern_features.py` |
| **App shell / shortcuts** | `frontend/src/App.tsx` | — |

---

## Master menu

| Window | UI module | Backend |
|--------|-----------|---------|
| Account Master Add / Modify | `features/account-master/` | `masters.py` |
| Standard Narration Master Add / Modify | `features/narration-master/` | `masters.py` (`list/get/save/delete_narration`) |
| City Master Add / Modify | `features/city-master/` | `masters.py` (`list/get/save/delete_city`) |
| Transport Master Add / Modify | `features/transport-master/` | `masters.py` (`list/get/save/delete_transport`) |
| Trading Account Add / Modify (menu: Trading Master) | `features/trading-account/` | `masters.py` (`list/get/save/delete_trading_account`, `list_items`) |
| Item Entry Add / Modify | `features/item-entry/` | `masters.py` (`list/get/save/delete_item`) |
| Opening Stock Entry / Closing Stock Entry | `features/stock-entry-master/` | `masters.py` (`stock_entry_master`, syncs `opening_stock`) |
| Bank Master Add / Modify | `features/bank-master/` | `masters.py` (`list/get/save/delete_bank`) |
| IFSC Master Add / Modify (menu: IFSC Code Master) | `features/ifsc-master/` | `masters.py` (`list/get/save/delete_ifsc`) |
| Expenses Master Define | `features/expense-master/` | `masters.py` (`list/get/save/delete_expense_master`) |
| I Form Expenses define | `features/i-form-expense-define/` | `masters.py` (`i_form_expense_define` table) |
| Cheque Print Setting | `features/cheque-print-setting/` | `masters.py` (`cheque_print_setting`) |

---

## Daily / vouchers (legacy bundle)

These forms live in **`features/legacy/EntryWindowImpl.tsx`** until split into `features/accounting/` and `features/mandi-vouchers/`:

| Window | Component name in legacy file |
|--------|-------------------------------|
| Cash Book | `CashBookForm` |
| Journal / Accounting Voucher | `JournalForm` |
| Debit Note / Credit Note Add / Modify | `features/accounting-note-entry/` | `accounting_note_entry.py` |
| Form - J | `FormJ` |
| Form - I (Dr.) / Sale Invoice | `SaleBill` |
| Form - I (Cr.) | `FormICredit` |
| Lifting Entry Add / Modify | `features/lifting-entry/LiftingEntryScreen.tsx` | `lifting_entry.py` (RPC on `api.py`) |
| Kachi Purchase Add / Modify | `features/kachi-purchase/KachiPurchaseScreen.tsx` | `kachi_purchase.py` (RPC on `api.py`) |
| Mandi Purchase Entry Add / Modify | `features/mandi-purchase-entry/` | `mandi_purchase_entry.py` |
| GST Purchase Entry Add / Modify | `features/gst-purchase-entry/` | `gst_purchase_entry.py` |
| Invoice Add / Modify | `features/invoice-entry/` | `invoice_entry.py` |
| GST Debit Note Add / Modify | `features/gst-debit-note-entry/` | `gst_debit_note_entry.py` |
| GST Credit Note Add / Modify | `features/gst-credit-note-entry/` | `gst_credit_note_entry.py` |
| GST Expense Voucher Add / Modify | `features/gst-expense-voucher-entry/` | `gst_expense_voucher_entry.py` |
| Sale Invoice (Ctrl+S), … | `SaleBill` in legacy or `DocumentForm` |

---

## Calculations (validate here)

| Topic | File | Tests |
|-------|------|-------|
| Quintals, tare, moisture, line amount | `backend/anaj_erp/calculations/mandi.py` | `tests/test_mandi_calculations_module.py` |
| Ledger invariants | — | `tests/test_ledger_balance_invariants.py` |
| Document posting | `backend/anaj_erp/documents.py`, `mandi_bills.py` | `tests/test_accounting_workflows.py` |

---

## Migration status

- [x] Routing registries under `app/routing/` (old root paths re-export)
- [x] Account Master feature module
- [x] Calculations package `calculations/mandi.py`
- [x] Entry implementation moved to `features/legacy/EntryWindowImpl.tsx`
- [x] **Phase 1 grain scaffold:** [mandi-monolith-audit.md](./mandi-monolith-audit.md), `features/shared/LegacyFormContainer`, target folders (`form-j-entry`, `gate-pass-entry`, …)
- [ ] **Phase 2:** Move FormJ, SaleBill, CashBook, JournalForm into feature screens; router cutover
- [ ] Split `EntryWindowImpl.tsx` into feature modules (use `tools/split_entry_window.py`)
- [ ] Move remaining `screens/*` into matching `features/*` folders
- [ ] Extract `account_master.py` from `masters.py` (see `tools/extract_account_master.py`)

---

## Cursor prompt examples

- “Change Account Master dropdown options” → `@frontend/src/features/account-master/constants.ts`
- “Fix opening balance save” → `@frontend/src/features/account-master/formState.ts` + `@backend/anaj_erp/masters.py` (`save_account_master`)
- “Adjust TCS formula” → `@backend/anaj_erp/calculations/mandi.py` + run `pytest tests/test_mandi_calculations_module.py`
