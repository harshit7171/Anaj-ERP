# Agent guide (Anaj ERP)

Before broad codebase search, read:

1. **[docs/architecture/CODEMAP.md](docs/architecture/CODEMAP.md)** — menu window → file paths  
2. **[docs/architecture/MODULE_LAYOUT.md](docs/architecture/MODULE_LAYOUT.md)** — folder conventions  

## Scoped work

| Task | Open only |
|------|-----------|
| Account Master UI | `frontend/src/features/account-master/` |
| Account Master save/load | `backend/anaj_erp/masters.py` (account methods) |
| Mandi math / TCS / TDS | `backend/anaj_erp/calculations/mandi.py` |
| New menu window | `frontend/src/app/routing/windowCatalog.ts` + feature folder under `frontend/src/features/` |
| Window routing alias | `frontend/src/app/routing/windowRouting.ts` |

## Do not

- Load entire `features/legacy/EntryWindowImpl.tsx` unless the target form is only defined there (see CODEMAP table).
- Change `api.py` RPC names without updating `frontend/src/api/remoteApi.ts` and types.

## Dev run

**Default while coding:** Assume dev mode is already up (Vite on 5173 + desktop with `ANAJ_ERP_DEV_URL`). **Do not rerun** after frontend-only edits — Vite HMR applies changes. Rerun **desktop only** after Python backend changes. See [docs/dev-without-rerun.md](docs/dev-without-rerun.md).

**User says rerun / run ERP / cold start:** attach [docs/cursor-rerun.md](docs/cursor-rerun.md) and run:

`powershell -ExecutionPolicy Bypass -File C:\Accblue_Software\tools\rerun_dev.ps1 -Agent`

Full detail: [docs/dev-run-reference.md](docs/dev-run-reference.md).

**Architecture:** Single-PC standalone by default; multi-company on local disk. LAN/office code is archived in `extra_code_Lan_Office/`. See [docs/standalone-mode.md](docs/standalone-mode.md).
