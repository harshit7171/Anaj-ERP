# Cursor: rerun Anaj ERP (attach this file)

**Repo:** `C:\Accblue_Software`  
**User says:** “rerun”, “run erp”, “run code”, “start dev” → do **only** what is below.

**While coding:** If Vite (5173) + desktop are already open, **do not rerun** — UI hot-reloads from Vite; restart desktop **only** after Python changes. See [dev-without-rerun.md](dev-without-rerun.md).

## One command (preferred)

```powershell
powershell -ExecutionPolicy Bypass -File C:\Accblue_Software\tools\rerun_dev.ps1 -Agent
```

- Ensures UI at `http://127.0.0.1:5173` (starts Vite if needed).
- Launches desktop: `python -m anaj_erp.main` with `ANAJ_ERP_DEV_URL`.
- Skip `npm install` / `pip install` if `.venv` and `node_modules` exist.

## If the script fails

| Step | Command |
|------|---------|
| Vite | `cd C:\Accblue_Software; npm run dev` (background) |
| Desktop | `cd C:\Accblue_Software; .\.venv\Scripts\Activate.ps1; $env:ANAJ_ERP_DEV_URL='http://127.0.0.1:5173'; python -m anaj_erp.main` (background) |

Port **5173 already in use** → Vite is already running; run **desktop step only**.

## Other quick commands

| Intent | Command |
|--------|---------|
| UI build check | `cd C:\Accblue_Software; npm run build` |
| Tests | `cd C:\Accblue_Software; .\.venv\Scripts\python.exe -m pytest -q` |
| Prod-like (no Vite) | `npm run build` then `python -m anaj_erp.main` **without** `ANAJ_ERP_DEV_URL` |

## Do not

- Re-read full README or scan the repo before rerun.
- Ask for approval unless the shell blocks the script (then retry the **same** script with user approval).

More detail: [dev-run-reference.md](dev-run-reference.md) · UI map: [architecture/CODEMAP.md](architecture/CODEMAP.md)
