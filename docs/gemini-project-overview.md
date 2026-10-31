# Anaj Accounting ERP — Project Overview for AI / External Review

**Repository:** `c:\Accblue_Software`  
**Audience:** Gemini or other reviewers who need a single accurate picture of what exists, what stack is used, and how ready the product is to sell.  
**Last updated:** October 2026 (reflects current source tree).

Use this document together with:

- `docs/accounting-spec.md` — full target workflows and accountant sign-off checklist  
- `docs/implementation-summary.md` — feature checklist (ignore any accidental chat text at the file end)  
- `docs/operator-guide.md` — day-to-day operator flows  
- `README.md` — dev setup, licensing vendor commands, build commands  

> **Note:** `docs/gemini-technical-handoff.md` is an older, longer handoff. It describes **USB two-device sync** (`sync.py`, `.anajsync` packages). That sync layer is **not in the current codebase**; legacy sync tables are dropped on migration. Current model is **standalone offline desktop** plus **`.anajbackup` backup/restore** (no live DB merge over pen drive).

---

## 1. What this product is

Offline **Windows desktop ERP** for **Haryana grain commission agents** (mandi-style accounting): keyboard-first entry, double-entry books, Form-J / Form-I, sale and purchase bills, stock, GST/TDS/mandi registers, PDF invoices, and **annual offline licensing** (Ed25519, no cloud).

**Not a web SaaS.** No server required for daily use. Data lives in SQLite under the Windows user’s roaming app data (`AnajERP`).

---

## 2. Technology stack

| Layer | Technology |
|--------|------------|
| Desktop shell | Python 3.11+ (dev/tested with 3.14), **pywebview** (Edge WebView2) |
| UI | **React 19**, **TypeScript**, **Vite 8**, **Tailwind CSS 4** |
| Backend / domain | Python packages under `backend/anaj_erp/` |
| Database | **SQLite only** (catalog DB + one DB per company), WAL, FK on, synchronous FULL — no MySQL |
| Money / quantities | Integer **paise**; fixed-point scaled integers for qty/weight |
| PDF / print | **ReportLab**, Windows default printer |
| Licensing | **cryptography** (Ed25519 verify on customer app; vendor signing in `tools/license_admin.py`) |
| Local secret protection | Windows **DPAPI** (license anti-rollback, vendor private key storage) |
| Packaging | **PyInstaller** (`AnajERP.spec`), **Inno Setup** (`installer/AnajERP.iss`) |
| Dev quality | **pytest**, **mypy**, **ruff**, TypeScript `tsc` + Vite build |

**Bridge:** React calls Python through pywebview’s `js_api` (`ApplicationApi` in `backend/anaj_erp/api.py`).

---

## 3. Architecture (short)

```text
React UI (frontend/src)
    ↓ pywebview bridge
ApplicationApi (api.py) — context, license gates, validation
    ↓
Services: accounting, documents, reports, credit, backup, maintenance, printing, licensing
    ↓
DatabaseManager (database.py) — catalog + per-company SQLite
```

**Data separation:** Program files vs books — company databases are **never** stored inside the install folder.

---

## 4. Functionality implemented (current)

### 4.1 Platform and startup

- Lord Ganesha welcome / startup artwork  
- Company list, create company, April–March financial years  
- Select company + year; create year; lock / audited reopen metadata  
- Blue accounting workspace, right-side shortcut panel, Entry menu  
- Keyboard: function keys, autocomplete (prefix search, Up/Down, Enter), grid Enter navigation  
- Settings modal, bento-style dashboard hooks, farmer credit dashboard UI  

### 4.2 Masters and rules

- Ledger accounts, parties (farmer, purchaser, customer, supplier, commission agent, transporter, etc.)  
- Commodities, varieties, HSN, bag weights, quantity scales  
- **Effective-dated charge rules** (%, fixed, basis: amount/bag/qty/weight, add/deduct, ledger mapping)  
- Charge-rule admin API (list, create, revise)  
- Master CSV import (dry-run + import) via maintenance service  
- Farmer **credit limits** with warning + override audit  

### 4.3 Accounting and documents

Shared engine posts (in one transaction where applicable): document, lines, stored charges, voucher lines, inventory movements, audit events.

**Vouchers:** Cash Book, Journal, balanced double-entry validation, **reversal** (no silent delete of posted history).

**Document types** (backend + UI entry menu; some screens share a generic dense form):

- Form-J (dedicated dense UI: Dheri rows, expenses, bonus, self-purchase, numbering)  
- Form-I Debit and Form-I Credit (dedicated sale-bill / inbound credit flows)  
- Sale / Purchase invoice and memos  
- Transfer challan, delivery challan, gate pass, inward/outward  
- Consignment Dr/Cr, milling inward/outward  
- Debit/credit notes, accounting voucher, and related labels in menu  

**Calculations:** Non-tax mandi charges, freight add/deduct, GST on configured bases, bonus direction per workflow; **snapshots stored on document** so old bills do not change when rules change.

### 4.4 Inventory

- Immutable movement rows, bag + quantity tracking  
- Idempotency keys per source line  
- Commodity / warehouse balance queries  

### 4.5 Reports and compliance (backend APIs)

Exposed via `ApplicationApi` (UI coverage varies):

- Trial balance, account ledger, account balance, cash book, day book  
- Stock balance, document registers (purchase, sale, Form-I, Form-J, challan)  
- GST / TDS / mandi-style tax register  
- P&L and balance sheet datasets, simple interest  
- Company reconciliation report  
- Monthly TDS compliance reminder (days 1–10) via `compliance_status`  

Some reports may still need **dedicated print/layout screens** matching legacy desktop software.

### 4.6 Printing

- A4 PDF with Original/Duplicate/Triplicate, line and charge breakdown, amount in words  
- Print to Windows default printer  

### 4.7 Licensing (customer-facing)

- Installation UUID shown on activation screen  
- Paste/install vendor-signed annual token (April 1 → April 30 next year model)  
- Signature verify, installation binding, expiry, warning phase  
- Clock rollback detection (DPAPI-backed last-use)  
- Expired license: read/history vs write lock behavior (covered in tests)  

**Vendor side:** `tools/license_admin.py` (init key pair, issue license) — **must not ship to customers**.

### 4.8 Backup, restore, migration

- `.anajbackup` online SQLite backup with SHA-256 and integrity/FK checks  
- Restore **only as new company** (never overwrite live books)  
- Pilot CSV dry-run and reconciliation tests  

### 4.9 Explicitly out of scope / removed in current tree

- **Encrypted USB sync** (`.anajsync`, pairing files, conflict UI) — described in old docs only; **not present** in `backend/anaj_erp/` today.  
- **Purchase Muttax** — menu label only until local business meaning and postings are confirmed (`accounting-spec.md`).  

---

## 5. Code size and quality signals

Approximate **source lines** (excluding dependencies):

| Area | Lines (approx.) | Files (approx.) |
|------|-----------------|-----------------|
| Python (`backend`, `tests`, `tools`) | ~5,900 | 20 |
| Frontend TS/TSX (`frontend/src`) | ~4,200 | 19 |

**Largest backend modules:** `documents.py`, `accounting.py`, `database.py`, `api.py`.

**Automated tests (October 2026):**

- **22 pytest tests**, all passing  
- **Backend line coverage ~69%** (whole `anaj_erp` package)  
- Weaker coverage areas: `main.py` (desktop entry), `reports.py` (~35%), parts of API error paths  

**Build / static checks (documented as passing in project notes):**

- `npm run build` (TypeScript + Vite)  
- `mypy backend`  
- `ruff check .`  
- PyInstaller produces `dist\AnajERP\AnajERP.exe`  

---

## 6. Completeness for selling (honest assessment)

This is **engineering completeness**, not legal certification.

| Dimension | Rough readiness | Comment |
|-----------|-----------------|--------|
| Core offline desktop app | **~85%** | Runnable dev stack; packaged EXE built; corporate GPO may block unsigned EXEs on some laptops |
| Mandi workflows (Form-J / Form-I / sale bill) | **~75%** | Strong dedicated UI + tests on golden-style scenarios; accountant must validate postings and rates |
| Generic document types | **~60%** | Engine supports many types; several reuse common forms vs legacy-specific screens |
| Reports (data) | **~65%** | Many report functions exist; UI/report presentation not fully productized |
| Reports (statutory layouts) | **~30%** | Needs Haryana-specific layouts and sign-off |
| Licensing & activation | **~85%** | Implemented and tested; needs vendor key custody and support process |
| Installer / distribution | **~70%** | Inno Setup script exists; **code signing** and support docs still required for retail |
| Backup / disaster recovery | **~80%** | `.anajbackup` path implemented; operator training needed |
| Multi-PC sync | **0% in current code** | Use backup/restore or separate companies per machine |
| **Legal / accountant approval** | **0% certified** | **Blocking for “safe to sell as compliant mandi software”** |

### Can you sell it today?

**Pilot / early adopter with written disclaimer:** Yes, if a qualified **Haryana mandi accountant** reviews rates, postings, rounding, and print formats, and the customer runs **parallel books** during pilot.

**General commercial release:** Not yet recommended until:

1. Accountant golden examples for **every** supported transaction type  
2. Statutory rate and GST/TDS/mandi rule approval per effective date  
3. Invoice PDF wording/layout sign-off  
4. Code-signed installer/EXE and license support runbook  
5. Real commission-agent pilot on production-like data volume  

---

## 7. Key files map (for navigation)

| Path | Role |
|------|------|
| `backend/anaj_erp/main.py` | Desktop entry, WebView window |
| `backend/anaj_erp/api.py` | All JS-callable API methods |
| `backend/anaj_erp/database.py` | Schema, migrations, connections |
| `backend/anaj_erp/accounting.py` | Masters, vouchers, balances |
| `backend/anaj_erp/documents.py` | Invoices, forms, charges, stock posting |
| `backend/anaj_erp/reports.py` | Report datasets |
| `backend/anaj_erp/licensing.py` | Customer license verify/install |
| `backend/anaj_erp/credit.py` | Farmer credit limits |
| `backend/anaj_erp/backup.py` | Backup/restore packages |
| `backend/anaj_erp/printing.py` | PDF generation |
| `frontend/src/App.tsx` | Startup, menus, shortcuts, license UI |
| `frontend/src/EntryWindow.tsx` | Transaction windows router |
| `frontend/src/DenseDocumentForm.tsx` | Shared dense accounting forms |
| `tests/test_accounting_workflows.py` | End-to-end posting scenarios |
| `tools/license_admin.py` | Vendor-only license issuance |

---

## 8. How to run (for reviewers)

From repo root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm install

# Terminal 1 — UI dev server
npm run dev

# Terminal 2 — full ERP window
$env:ANAJ_ERP_DEV_URL = "http://127.0.0.1:5173"
python -m anaj_erp.main
```

Production-like (no dev server): `npm run build` then `python -m anaj_erp.main` (loads `frontend/dist`).

---

## 9. Suggested prompt for Gemini

Copy this with the document:

> You are reviewing **Anaj Accounting ERP**, an offline Windows pywebview + React + Python + SQLite system for Haryana grain commission agents. Using the attached overview and `docs/accounting-spec.md`, produce: (1) a gap list vs full mandi ERP expectations, (2) accounting correctness questions for a qualified accountant, (3) security/licensing review, (4) UI/workflow priorities, (5) a phased roadmap to **pilot-ready** vs **retail-ready** sale. Do **not** assume USB sync exists in the current repo. Preserve offline operation, integer paise, immutable posted history with reversals, and effective-dated charge rules. Separate **facts from assumptions**.

---

## 10. Invariants reviewers must not break

- Offline-first; no mandatory cloud  
- Money in integer paise, not float  
- Posted vouchers must balance; corrections via reversal/audit  
- Document charges stored at post time  
- No overwriting live company DB on restore  
- Vendor private signing key never in customer build or git  
