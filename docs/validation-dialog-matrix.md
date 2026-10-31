# Validation and message dialogs

| Screen | Trigger | Message | Implementation |
|--------|---------|---------|----------------|
| All Daily | Save with missing required field | Please enter required details. | Backend `ValidationError` → form error text |
| All Daily | Successful post | Data has been Successfully Saved | `SavedModal` in EntryWindow / DenseDocumentForm |
| All Daily | Print before post | Save the document before printing. | `MessageDialog` in DenseDocumentForm |
| Cash Book | No lines on save | Enter at least one receipt or payment. | CashBookForm validation |
| Journal | Unbalanced / &lt;2 lines | Debit and credit totals must be equal. | JournalForm validation |
| Credit limit | Breach on post | Credit limit modal | `CreditLimitWarningModal` |
| License | Expired / tamper | Blocking toast / modal | `LicenseNotice` in App.tsx |

Esc closes transaction modals via `TransactionWindowModal` → `Modal`.

Extract additional screenshot-specific prompts during pilot and append rows here.
