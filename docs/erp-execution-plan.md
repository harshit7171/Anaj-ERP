# Anaj ERP — Execution plan (SQLite only)

Canonical copy for the repo. Cursor plan mirror: `erp_parity_and_mysql_b2e3dd32.plan.md` (content updated to remove MySQL).

## Database

**SQLite only** — [`backend/anaj_erp/database.py`](../backend/anaj_erp/database.py). Additive migrations. Multi-user via **FastAPI + shared SQLite on office PC** (Phase 8). No MySQL.

## Execution order

1. **Phase 0** — Screenshot index, parity matrix, calculation spec, validation dialog matrix  
2. **Phase 1** — Modal pads, Enter flow, PDF print (no `window.print`), MessageDialog  
3. **Phase 3** — Masters  
4. **Phase 4** — Daily transactions  
5. **Phase 5** — Search + Tools  
6. **Phase 6** — Reports 1 & 2  
7. **Phase 7** — GST reports  
8. **Phase 8** — Multi-user LAN API + users/Munim  
9. **Phase 9** — Pilot, packaging, accountant review  

## Batch execution

Run phases in order without per-screen approval. Pause only on hard blockers or explicit user direction.

## Pre-approved

- Pakki/Kachi = separate companies; hide Kachi in settings  
- Sky-blue UI; Esc/× modals; no horizontal grid scroll  
- Print bills via ReportLab PDF from posted data only  
- Integer paise; reversals; effective-dated charges  

See [implementation-progress.md](implementation-progress.md) for current status.
