# Module layout (Anaj ERP)

This repo uses **feature-first** folders. Each menu window maps to a module under `frontend/src/features/` and (when applicable) `backend/anaj_erp/domains/`.

## Frontend (`frontend/src/`)

| Path | Purpose |
|------|---------|
| `app/` | Shell: routing, window resolution, entry router (no business UI). |
| `app/routing/` | `menuRegistry`, `windowRouting`, `reportRegistry`, `windowCatalog`. |
| `app/entry/` | `EntryWindow.tsx`, `resolveEntry.tsx` — pick screen by menu title. |
| `features/<name>/` | One product area: UI + hooks + API types + constants for that page. |
| `shared/` | Cross-feature UI, hooks, utils, desktop API types. |
| `legacy/` | Temporary re-exports only; do not add new code here. |

### Feature folder template

```
features/<feature-id>/
  README.md          # What this screen does, shortcuts, backend RPC names
  index.ts           # Public exports (screen + registry hook)
  <Feature>Screen.tsx
  types.ts
  api.ts             # pywebview / LAN RPC wrapper for this feature only
  constants.ts
  hooks/             # Optional local state
  components/        # Optional sub-UI used only here
```

## Backend (`backend/anaj_erp/`)

| Path | Purpose |
|------|---------|
| `api.py` | Thin pywebview façade; delegates to domains/services. |
| `domains/` | Business logic grouped by ERP area (masters, documents, reports). |
| `calculations/` | Pure formulas (mandi weight, TCS/TDS, line amounts) — safe to validate in isolation. |
| `accounting.py`, `documents.py`, … | Core services (being split into `domains/` over time). |

## How to change one page

1. Open **`docs/architecture/CODEMAP.md`** → find the menu label → **UI path** + **backend path**.
2. Edit only that feature folder (+ its domain file on the backend).
3. Run focused tests listed in the feature `README.md`.

## Cursor / AI

Point the agent at a **single path**, e.g.:

- `frontend/src/features/account-master/` — Account Master Add/Modify UI
- `backend/anaj_erp/domains/masters/account_master.py` — save/load/delete account master
- `backend/anaj_erp/calculations/mandi.py` — mandi calculation formulas

Avoid reading `EntryWindow` legacy bundles; use `app/entry/resolveEntry.tsx` and `windowCatalog.ts` instead.
