# Form - J (farmer / dheri / mandi purchase slip)

**Status:** Phase 2 — extracted from `EntryWindowImpl.tsx`.

**UI:** `FormJEntryScreen.tsx` + `LegacyFormContainer` (F12 save, F3 refresh calc, F4 exit).

**State:** `useFormJEntry.ts` — debounced `calculate_document` for Market Fee, HRDF, TCS, TDS, etc.

**Backend:** `post_document` / `calculate_document`, `document_type: form_j` → charge engine + `calculations/mandi.py`.

**Shortcuts:** Enter-as-Tab, grid Enter new dheri, Ctrl+F self-purchase.

See [mandi-monolith-audit.md](../../../docs/architecture/mandi-monolith-audit.md).
