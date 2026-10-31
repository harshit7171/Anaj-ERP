# Masters domain

| Submodule | Status | Location |
|-----------|--------|----------|
| Account Master | **Canonical UI** → `frontend/src/features/account-master/` | Persistence: `masters.py` methods `save_account_master`, `get_party_master`, `get_account_master`, `delete_account_master` (extract to `account_master.py` next) |
| City / Transport / Bank / Item / … | Implemented | `backend/anaj_erp/masters.py` (`MasterService`) |

When editing **Account Master** backend rules, search `masters.py` for `save_account_master` and `_ACCOUNT_METADATA_KEYS`.
