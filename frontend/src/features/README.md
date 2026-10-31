# Features (UI by product area)

Each subdirectory is one **menu family** or **screen group**. Prefer editing only that folder + the backend path listed in its `README.md` or in [CODEMAP](../../../docs/architecture/CODEMAP.md).

| Folder | Screens |
|--------|---------|
| `shared/` | `LegacyFormContainer`, `useLegacyFormKeyboard` (Phase 1 grain scaffold) |
| `account-master/` | Account Master Add / Modify |
| `kachi-purchase/`, `lifting-entry/`, `mandi-purchase-entry/` | Extracted daily grain forms |
| `form-j-entry/`, `cash-book-entry/`, `form-i-debit-entry/`, … | Phase 1 scaffolds (logic still in legacy until Phase 2) |
| `legacy/` | Temporary bundle of Entry/Daily forms (`EntryWindowImpl.tsx`) |

**Audit:** [docs/architecture/mandi-monolith-audit.md](../../docs/architecture/mandi-monolith-audit.md)

**Planned** (see CODEMAP migration): split remaining monolith forms; optional `mandi-vouchers/` grouping.
