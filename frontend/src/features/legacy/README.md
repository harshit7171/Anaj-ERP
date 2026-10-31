# Legacy entry bundle

`EntryWindowImpl.tsx` contains most **Entry / Daily / Search** forms in one file (~2k lines).

**Do not add new screens here.** Add a folder under `features/<name>/` and register in `app/routing/windowCatalog.ts`.

Split plan: run `python tools/split_entry_window.py` (maintainer tool) to generate `features/accounting/forms/*` and `features/mandi-vouchers/forms/*`.
