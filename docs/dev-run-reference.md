# Dev run reference (attach this file to save tokens)

**Repo root:** `C:\Accblue_Software`  
**Stack:** Vite React UI + `pywebview` desktop shell (`python -m anaj_erp.main` / console script `anaj-erp`).

## Prerequisites

- Python 3.11+ (project uses `py -3.14` where noted)
- Node.js LTS
- Edge WebView2 Runtime (Windows)
- Existing `.venv` and `node_modules` (see one-time setup)

## One-time setup (skip if `.venv` and `node_modules` exist)

```powershell
cd C:\Accblue_Software
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm install
```

## Daily development (preferred — hot reload UI)

**Terminal 1 — Vite**

```powershell
cd C:\Accblue_Software
npm run dev
```

Serves UI at `http://127.0.0.1:5173`.

**Terminal 2 — desktop window**

```powershell
cd C:\Accblue_Software
.\.venv\Scripts\Activate.ps1
$env:ANAJ_ERP_DEV_URL = "http://127.0.0.1:5173"
python -m anaj_erp.main
```

Equivalent: `anaj-erp` after venv activate and `ANAJ_ERP_DEV_URL` set.

Optional debug: `$env:ANAJ_ERP_DEBUG = "1"`

## Production-like (no Vite)

```powershell
cd C:\Accblue_Software
npm run build
.\.venv\Scripts\Activate.ps1
python -m anaj_erp.main
```

Do **not** set `ANAJ_ERP_DEV_URL`; app loads `frontend/dist`.

## Office LAN server (multi-user)

```powershell
pip install -e ".[server]"
$env:ANAJ_ERP_ADMIN_PASSWORD = "YourBootstrapPassword"
anaj-erp-server
```

Details: [lan-server-setup.md](lan-server-setup.md). Desktop clients use **Office server (LAN)** on startup.

## Data storage (SQLite)

Resolved in `anaj_erp.data_paths` (used by `DatabaseManager` — not hardcoded in the UI):

1. Explicit path passed to `DatabaseManager(...)` (tests, smoke tools)
2. `ANAJ_ERP_DATA_DIR` environment variable
3. Existing `D:\MandiERP\Data` or `E:\MandiERP\Data` (customer site setup creates this folder)
4. Roaming AppData (`AnajERP` via platformdirs)

SQLite pragmas on every app connection: `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `ANAJ_ERP_DATA_DIR` | Override data root (catalog + companies); also used if D/E MandiERP folders are absent |
| `ANAJ_ERP_DEV_URL` | Dev UI URL (e.g. `http://127.0.0.1:5173`) |
| `ANAJ_ERP_DEBUG` | `1` / `true` for extra logging |
| `ANAJ_ERP_ADMIN_PASSWORD` | Bootstrap admin on first LAN server start |
| `ANAJ_ERP_DATA_DIR` | Shared data path (LAN server) |
| `ANAJ_ERP_HOST` / `ANAJ_ERP_PORT` | LAN bind (default `0.0.0.0:8765`) |

## Licensing, QA & release (Phase 7)

- **Demo**: 15-day full demo on first install (`phase: demo`); after expiry, writes lock until license key.
- **License key**: asymmetric Ed25519 — issue with `python tools/issue_license.py` (vendor private PEM).
- **Fleet portal**: `ANAJ_FLEET_ADMIN_TOKEN`, `ANAJ_FLEET_PRIVATE_KEY_PEM` → `anaj-fleet-portal` (port 8870).
- **Release build**: `.\tools\build_release.ps1` — see [release-build-pipeline.md](release-build-pipeline.md).
- **Parity audit**: `python tools/run_parity_audit.py` → `docs/parity-audit-miracle-aarath-marg.md`.
- **Formula tests**: `tests/test_mandi_calculations_module.py`, `tests/test_ledger_balance_invariants.py`.

## LAN, GST, cloud & mandi online (Points 11–13, 24)

- **Master PC**: `anaj-erp-server` or desktop with `ANAJ_ERP_EMBED_LAN_SERVER=1` — HTTP `:8765`, WebSocket `/ws/live`, UDP discovery `:8766`.
- **Munim laptops**: startup → Office server → **Auto-discover master PC** or enter `http://<ip>:8765`.
- **GSTIN lookup**: Masters / Company Parameters — provider AppyFlow, **GST sandbox**, or custom URL; party masters use **Fetch GST** (15-digit GSTIN).
- **Cloud backup**: Tools → **Cloud Backup** — passphrase, OAuth device link (Google / OneDrive), optional **backup on exit** (`.bak.enc`).
- **Mandi bhav / boli**: Daily → **Mandi Bhav Online**, **Live Boli Board** (TV variant for shop display). Set `agmarknet_api_key` for live Agmarknet rows.

## Export & printing (Phase 5)

- Reports: run any catalog report, then **Export CSV/XLSX/PDF/DOCX/XML/HTML/PNG/JPEG** (server-side, no MS Office).
- Mandi bills: **Tools → Print Format Designer** for headers, mandi license, bank QR text, terms.
- Document print (F7): optional **3-copy** PDF or **ESC/POS** raw (`80`/`132` col); column toggles for moisture/tare; enable **Auto-print copies when voucher saves** in the print sidebar.
- Ledger print API: `print_party_ledger` (Muddat Bilti / Nakal Khata PDF).
- Optional packages: `pip install -e ".[export]"` (openpyxl, python-docx, Pillow). Included in `.[dev]`.

## Quick checks

```powershell
.\.venv\Scripts\Activate.ps1
pytest
python tools/pilot/smoke_pilot.py
```

## Agent instructions

**Fast rerun (attach [cursor-rerun.md](cursor-rerun.md) instead of this whole file):**

```powershell
powershell -ExecutionPolicy Bypass -File C:\Accblue_Software\tools\rerun_dev.ps1 -Agent
```

When the user attaches **this file** and asks to run or test locally:

1. Assume repo root `C:\Accblue_Software`; do not re-read full README unless something fails.
2. If `.venv` and `node_modules` exist, skip install.
3. Prefer `tools\rerun_dev.ps1 -Agent` over manual two-terminal steps.
4. For headless/CI-only checks, prefer `pytest` or `npm run build` instead of opening the window.

## Related docs

- [operator-guide.md](operator-guide.md) — daily use
- [other-laptop-setup.md](other-laptop-setup.md) — packaged install / licensing
- [gemini-project-overview.md](gemini-project-overview.md) §8 — reviewer run steps
