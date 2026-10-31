# Anaj ERP — Visual system map (lifecycle & dependencies)

Box-style architecture similar to an **incident/resolution lifecycle**: numbered steps left → right, **data stores** at the bottom, **UI zones** grouped, and **status colours** on every major block.

**How to view:** Open this file in Cursor / GitHub / any Mermaid preview. Colours use `classDef` (green / yellow / red).

**Companion doc:** [project-status-and-architecture.md](../project-status-and-architecture.md)

---

## Legend

| Colour | Meaning | Examples |
|--------|---------|----------|
| 🟩 **Green (`done`)** | Shipped and wired end-to-end (UI ↔ API ↔ DB) | Account Master, Voucher Entry, GST report screens |
| 🟨 **Yellow (`wip`)** | Works but incomplete, simplified logic, or still in legacy shell | Legacy forms in `EntryWindowImpl`, GST numbers depth, old forms not split |
| 🟥 **Red (`todo`)** | Not built or not production-ready | Live GSTR-2B download, full gov GSTR-1, LAN mode, signed installer |

---

## 1. End-to-end lifecycle (menu → post → report)

*Historical master data and lookups first, then screen-specific autofill, then post to SQLite, then read-only reports.*

```mermaid
flowchart LR
  subgraph phase1 ["① OPEN WINDOW"]
    U[User menu / F-key] --> M[menuRegistry]
    M --> R[windowRouting]
    R --> E[EntryWindowImpl router]
  end

  subgraph phase2 ["② PICK UI SURFACE"]
    E --> F1[features/* entry screens]
    E --> F2[LegacyReportScreen]
    E --> F3[GstReportScreen]
    E --> F4[DenseDocumentForm / legacy forms]
    E --> F5[Tools / Dashboard]
  end

  subgraph phase3 ["③ AUTOFILL & VALIDATE"]
    F1 --> AC[Autocomplete search_master]
    F1 --> LK[lookup_* RPC per screen]
    AC --> MS[(Master tables)]
    LK --> MS
    LK --> DOC[(Posted documents history)]
    F1 --> CALC[mandi.py / document calc]
  end

  subgraph phase4 ["④ POST (WRITE)"]
    F1 --> API[api.py]
    F4 --> API
    API --> DOM[documents.py accounting.py *_entry.py]
    DOM --> TXN[SQLite transaction]
    TXN --> CDB[(Company DB)]
  end

  subgraph phase5 ["⑤ REPORTS (READ)"]
    F2 --> RUN[run_report]
    F3 --> RUN
    RUN --> CAT[report_catalog.py]
    CAT --> RP[reports.py]
    CAT --> GST[gst_report_pages.py]
    RP --> CDB
    GST --> CDB
  end

  class U,M,R,E done
  class F1,F2,F3,F5 done
  class F4 wip
  class AC,MS done
  class LK wip
  class API,DOM,TXN,CDB done
  class CALC done
  class RUN,CAT,RP done
  class GST wip
  class DOC done
```

**Narrative (same as the diagram title on your reference slide):**  
**Masters + posted history first** → **screen lookups / rates** → **post voucher/document** → **reports read posted data only** (no silent re-calc of old bills).

---

## 2. Data stores (bottom layer)

```mermaid
flowchart TB
  subgraph stores ["PERSISTENCE"]
    CATDB[(Catalog DB<br/>companies, license, paths)]
    CDB[(Company DB<br/>masters + posted docs)]
    BLOB[(document_attachment<br/>local files)]
    BACKUP[(.anajbackup / Drive folder<br/>optional)]
  end

  APP[Desktop app pywebview] --> CATDB
  APP --> CDB
  DOM[documents / accounting / masters] --> CDB
  DOM --> BLOB
  TOOLS[Tools backup] --> BACKUP

  class CATDB,CDB,BLOB done
  class BACKUP wip
  class APP,DOM,TOOLS done
```

| Store | Holds | Used by |
|-------|--------|---------|
| **Catalog DB** | Company list, active FY pointer | Startup, company switch |
| **Company DB** | `party`, `account`, `commodity`, `document`, `document_line`, `document_charge`, `voucher`, `stock_movement`, … | All entry + reports |
| **Attachments** | Scanned bills, files | API attach; UI hook partial |
| **Backup** | Zip packages, optional cloud copy | Tools menu |

---

## 3. Autofill & lookup pipeline

Two patterns work together:

1. **Generic** — `Autocomplete` → `search_master(entityType)` → account / party / commodity rows.  
2. **Contextual** — each entry screen calls **`lookup_*`** (party → item → **rate** from last posted lines).

```mermaid
flowchart TB
  subgraph ui ["UI FIELD"]
    IN[User types in party / item / rate]
  end

  subgraph pathA ["PATH A — Generic master search"]
    IN --> A1[Autocomplete.tsx]
    A1 --> SM[api.search_master]
    SM --> M1[(party / account / commodity)]
  end

  subgraph pathB ["PATH B — Screen-specific chain"]
    IN --> B1[Feature screen e.g. Lifting / Mandi / GST]
    B1 --> B2[lookup_*_parties]
    B2 --> B3[lookup_*_items]
    B3 --> B4[lookup_*_rates]
    B4 --> HIST[Last rates/qty from document_line + metadata]
    HIST --> M1
    HIST --> DOC[(posted document)]
  end

  subgraph pathC ["PATH C — External GSTIN optional"]
    AM[Account / Transport Master] --> GSTIN[Enter GSTIN]
    GSTIN --> WEB[AppyFlow API if key set]
    WEB --> FILL[Name address PAN fill]
  end

  subgraph post ["After user confirms"]
    B1 --> SAVE[save_* / post_document]
    SAVE --> DOC
  end

  class A1,SM,M1 done
  class B1,B2,B3 done
  class B4,HIST wip
  class AM,GSTIN done
  class WEB,FILL wip
  class SAVE,DOC done
```

| Autofill area | Status | Notes |
|---------------|--------|--------|
| Party / account / commodity search | 🟩 | `search_master` |
| GST purchase / invoice / GST DN-CN parties & items | 🟩 | Dedicated RPCs |
| Mandi / Lifting line parties & items | 🟩 | Dedicated RPCs |
| **Lifting / Mandi line rate autofill** | 🟨 | RPC exists; parity with legacy “Rate autofill” UX may need tuning |
| GSTIN fetch (internet) | 🟨 | Needs API key in company settings |
| Unified lookup API (one RPC for all screens) | 🟥 | Many duplicate `lookup_*_parties` today |

---

## 4. UI router — what depends on what

```mermaid
flowchart TB
  SHELL[App.tsx + shortcuts]

  SHELL --> MENU[menuRegistry.ts]
  MENU --> ROUTER[EntryWindowImpl.tsx]

  ROUTER --> AM[account-master]
  ROUTER --> ITEM[item-entry]
  ROUTER --> LIFT[lifting-entry]
  ROUTER --> MAN[mandi-purchase-entry]
  ROUTER --> KAC[kachi-purchase]
  ROUTER --> GP[gst-purchase-entry]
  ROUTER --> INV[invoice-entry]
  ROUTER --> GDN[gst-debit-note-entry]
  ROUTER --> GCN[gst-credit-note-entry]
  ROUTER --> GEV[gst-expense-voucher-entry]
  ROUTER --> VOU[voucher-entry]
  ROUTER --> TDS[tds-challan-entry]
  ROUTER --> BNK[bank-reconciliation]
  ROUTER --> SRC[search-screens]
  ROUTER --> LEG[legacy forms in EntryWindowImpl]
  ROUTER --> DEN[DenseDocumentForm]
  ROUTER --> LR[LegacyReportScreen]
  ROUTER --> GR[GstReportScreen]
  ROUTER --> TL[ToolsScreens / Dashboard]

  ITEM -.->|commodity_id HSN| LIFT
  ITEM -.-> MAN
  ITEM -.-> GP
  ITEM -.-> INV
  AM -.->|party account| VOU
  AM -.->|party GSTIN| GP
  AM -.-> INV
  LIFT -->|posted lifting_entry| DOC[(documents)]
  MAN --> DOC
  GP --> DOC
  INV --> DOC
  VOU -->|voucher| DOC
  DOC --> LR
  DOC --> GR

  class SHELL,MENU,ROUTER done
  class AM,ITEM,LIFT,MAN,KAC,GP,INV,GDN,GCN,GEV,VOU,TDS,BNK,SRC done
  class LEG,DEN wip
  class LR done
  class GR wip
  class TL done
  class DOC done
```

**Dependency rules (for builders):**

- **Item Entry** → almost every **purchase/sale line** (commodity, HSN, bag weight).
- **Account Master** → **vouchers**, party GL links, GSTIN on reports.
- **Posted documents** → **all GST / accounting reports** (reports never edit history).
- **Charge rows on post** → GST registers & tax columns (quality of GST reports depends on this).

---

## 5. UI page clusters — status board

```mermaid
flowchart TB
  subgraph masters ["MASTER MENU"]
    M1[Account City Transport Trading Item Bank IFSC Expense I-Form Cheque Narration Stock entry]
  end

  subgraph daily ["DAILY / ENTRY"]
    D1[Split screens: Lifting Kachi Mandi GST Pur Invoice GST DN/CN GST Exp Voucher TDS Bank recon Acct DN/CN]
    D2[Legacy: Cash Book Form-J Form-I SaleBill Challans ...]
  end

  subgraph search ["SEARCH"]
    S1[Find Account Depreciation Stock Adj Letter Head]
  end

  subgraph reports ["REPORTS"]
    R1[LegacyReportScreen registers TB P and L interest stock ...]
    R2[GstReportScreen 14 menus]
  end

  subgraph tools ["TOOLS / HOME"]
    T1[Backup Dashboard WhatsApp reminders Clause 44 tools Cover print]
  end

  subgraph future ["NOT IN SCOPE / TODO"]
    N1[LAN multi-user live]
    N2[GSTR-2B GSTN download]
    N3[Full GSTR-1 file all sections]
    N4[WhatsApp Business API]
    N5[Code-signed installer golden pilot]
  end

  class M1,D1,S1,R1,T1 done
  class D2 wip
  class R2 wip
  class N1,N2,N3,N4,N5 todo
```

---

## 6. Backend service map (boxes)

```mermaid
flowchart LR
  API[api.py façade]

  API --> MST[masters.py]
  API --> DOC[documents.py]
  API --> ACC[accounting.py]
  API --> ENT["*_entry.py modules"]
  API --> CALC[calculations/mandi.py]
  API --> RC[report_catalog.py]
  RC --> RPT[reports.py]
  RC --> GRP[gst_report_pages.py]
  API --> MOD[modern_features.py tools dashboard]

  MST --> DB[(Company DB)]
  DOC --> DB
  ACC --> DB
  ENT --> DOC
  ENT --> ACC
  CALC --> DOC
  RPT --> DB
  GRP --> DB

  class API,MST,DOC,ACC,ENT,CALC,RC,RPT,MOD done
  class GRP wip
  class DB done
```

| Module | Status | Role |
|--------|--------|------|
| `masters.py` | 🟩 | CRUD masters, stock entry sync |
| `documents.py` + `accounting.py` | 🟩 | Post documents & vouchers |
| `*_entry.py` | 🟩 | Form-shaped save/load/search |
| `calculations/mandi.py` | 🟩 | Mandi weights, fees, TCS/TDS |
| `report_catalog.py` + `reports.py` | 🟩 | General reports |
| `gst_report_pages.py` | 🟨 | GST **UI columns** done; **statutory depth** yellow |
| `domains/` split | 🟥 | Target layout; migration incomplete |
| `extra_code_Lan_Office/` | 🟥 | LAN server archived |

---

## 7. GST report sub-lifecycle (read path)

```mermaid
flowchart LR
  U[User: GST Reports menu] --> G[GstReportScreen]
  G --> SCH[gstReportSchemas.ts filters]
  SCH --> P[buildParams party dates toggles]
  P --> RUN[run_report report_key]
  RUN --> CAT[report_catalog]
  CAT --> GRP[gst_report_pages.py]
  GRP --> Q[SQL on document + document_line + document_charge + party]
  Q --> FMT[Display columns + footer / sections]
  FMT --> GRID[Grid Excel Print JSON]

  class U,G,SCH,P,RUN,CAT done
  class GRP wip
  class Q,FMT done
  class GRID done

  subgraph gst_depth ["Statutory depth still 🟥/🟨"]
    X1[2B API import]
    X2[HSN tax split per line]
    X3[Full GSTR-1 JSON schema]
  end

  GRP -.-> X1
  GRP -.-> X2
  GRP -.-> X3
  class X1,X3 todo
  class X2 wip
```

---

## 8. One-page checklist (copy for slides)

| Layer | 🟩 Done | 🟨 In progress | 🟥 To do |
|-------|---------|----------------|----------|
| **Database** | SQLite catalog + company, paise, posting, audit | Backup cloud polish | — |
| **Autofill** | search_master, per-screen lookups | Rate autofill parity, GSTIN API | Unified lookup RPC |
| **UI — Masters** | Feature folders for major masters | — | Full 147-screen pixel parity |
| **UI — Daily** | 15+ split entry screens | Legacy bundle in EntryWindowImpl | Extract remaining forms |
| **UI — Search** | 4 screens | — | — |
| **UI — Reports** | Legacy + GST shells | GST tax accuracy, registers | — |
| **UI — Tools** | Dashboard, backup, WhatsApp link | Attachments UI | WhatsApp Business API |
| **Backend** | api + entry modules + reports | gst_report_pages depth | domains refactor, LAN |
| **Release** | Dev rerun, pytest | Pilot checklists | Signed installer, golden files |

---

## 9. Keeping this diagram honest

When you finish a feature:

1. Change its node from `wip` → `done` (or `todo` → `wip`) in the Mermaid `class` lines.
2. Update [project-status-and-architecture.md](../project-status-and-architecture.md) §3–4.
3. Update [CODEMAP.md](./CODEMAP.md) if paths changed.

*Generated for Accblue / Anaj ERP desktop codebase — standalone single-PC mode.*
