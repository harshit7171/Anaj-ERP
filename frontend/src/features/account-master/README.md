# Account Master (Add / Modify)

## Menu windows

- `Account Master Add` — shortcut **Ctrl+A** (when not typing in a field)
- `Account Master Modify`

## UI files

| File | Role |
|------|------|
| `AccountMasterScreen.tsx` | Layout, save/find/delete, keyboard shortcuts |
| `formState.ts` | Default form, load/save field mapping |
| `constants.ts` | Dropdown option lists (`MAIN_HEADS`, GST type, etc.) |
| `api.ts` | Desktop / LAN RPC wrapper |
| `components/Fields.tsx` | Reusable field widgets |

## Backend (validate formulas & persistence here)

| File | RPC methods |
|------|-------------|
| `backend/anaj_erp/domains/masters/account_master.py` | save, get, delete, record shaping |
| `backend/anaj_erp/api.py` | `save_account_master`, `get_party_master`, `get_account_master`, `delete_account_master` |

## Tests

- `pytest tests/test_accounting_workflows.py` (if account flows covered)
- Manual: Master → Account Master Add/Modify
