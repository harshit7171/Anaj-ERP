# Phase 2.4 — DenseDocumentForm commodity logic audit

**File:** `frontend/src/DenseDocumentForm.tsx`  
**Backend calc:** `backend/anaj_erp/calculations/mandi.py` via `calculate_document` / `documents.py`

## Finding: no hardcoded Paddy/Wheat moisture rules

| Area | Behaviour | Commodity-specific? |
|------|-----------|---------------------|
| Gate / Inward / Outward | `netWeight = grossWeight - tareWeight` (column formula) | **No** — generic weights |
| `moistureCode` | Free-text column on gate lines | **No** — not tied to item name |
| `qtlFromBags` | `(bags×pack + extra)/100` | **No** |
| Charge preview | Server `calculate_document` + expense master rules | **No** in React config |

Paddy/Wheat flags live in **Item Master** (`features/item-entry/` — `paddy`, `wheat` Y/N fields) and I-Form expense screens, not in DenseDocumentForm configs.

## Recommended follow-ups (Item Master, not dense form)

1. When moisture deduction becomes a business rule, store **moisture % / deduction formula** on `commodity` (or expense master) and apply in `mandi.py`, not in JSX.
2. Gate pass `moistureCode` can later autocomplete from commodity master if a `moisture_code` column is added.

## Phase 2 status

- **Form - J:** extracted to `features/form-j-entry/` with `calculate_document` debounce (mandi fees intact).
- **Mandi Purchase:** state in `useMandiPurchase.ts`; line sync via `recalcMandiLine`.
- **Dense forms:** unchanged routing via `supportsDenseDocument`; audit confirms no commodity hardcoding to remove.
