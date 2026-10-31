# Develop without rerunning the ERP (save tokens & time)

Run the stack **once** in the morning (or once per session). While it stays open, most coding **does not** need `rerun_dev.ps1` or the agent “run ERP” step.

## One-time start (you or agent — only when nothing is running)

```powershell
powershell -ExecutionPolicy Bypass -File C:\Accblue_Software\tools\rerun_dev.ps1 -Agent
```

Or manually:

1. **Terminal A:** `cd C:\Accblue_Software` → `npm run dev` (leave running)
2. **Terminal B:** activate `.venv`, `$env:ANAJ_ERP_DEV_URL='http://127.0.0.1:5173'`, `python -m anaj_erp.main`

Port **5173 already in use** → Vite is up; start **only** the desktop (Terminal B).

---

## After you change code

| You changed | Rerun full ERP? | What to do |
|-------------|-----------------|------------|
| **React/TS/CSS** under `frontend/src/` | **No** | Vite **HMR** updates the open window (often instant). If something looks stale, press **Ctrl+R** in the ERP window. |
| **Only docs / tests** | **No** | No app restart. |
| **Python** under `backend/anaj_erp/` (`api.py`, `*_entry.py`, reports, …) | **Desktop only** | Close the ERP window → run **Terminal B** again (same `ANAJ_ERP_DEV_URL`). **Do not** stop Vite. |
| **`npm run build` / production UI** | **Yes** | Unset `ANAJ_ERP_DEV_URL` or rebuild; different mode — use only for release checks. |
| **First install / missing deps** | **Yes** | `pip install -e ".[dev]"`, `npm install`, then start script. |

---

## Tell Cursor / the agent

Add to your prompt or project rules:

> **Do not rerun the ERP** unless I say “rerun”, backend Python changed, or the dev window was closed. Assume Vite on 5173 and desktop with `ANAJ_ERP_DEV_URL` are already running.

Attach **[cursor-rerun.md](cursor-rerun.md)** only when you actually need a start.

---

## Quick checks without opening the app

```powershell
cd C:\Accblue_Software
.\.venv\Scripts\python.exe -m pytest -q
cd frontend; npm run build
```

Use these instead of rerunning the desktop when validating changes.

---

## Why this works

With `ANAJ_ERP_DEV_URL`, the desktop shell loads **`http://127.0.0.1:5173`**, not `frontend/dist`. Vite watches files and pushes updates — no rebuild, no second full agent rerun.

Python runs **inside** the desktop process; there is no hot reload for the backend yet — restart **only** that process when you touch `.py` files.
