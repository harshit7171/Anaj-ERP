# Shared feature utilities (Phase 1 grain ERP)

## `LegacyFormContainer`

Wraps migrated mandi/daily forms with:

- `accounts-entry-screen` layout (`accounts-entry.css`)
- **Enter → Tab** via `useFormEnterFlow`
- **F2** Save (or **F3** when `saveOnF3` — lifting/mandi style)
- **F3** View / preview when not using `saveOnF3`
- **F4** Cancel / exit
- **F7** Print (optional)
- **F12** Save when `saveOnF12` (TransactionScreen parity)

## `useLegacyFormKeyboard`

Attach the same F-key map to custom forms that cannot use the container yet.

Audit & migration order: [docs/architecture/mandi-monolith-audit.md](../../../docs/architecture/mandi-monolith-audit.md).
