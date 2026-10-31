# Anaj ERP Operator Guide

## Starting the software

1. Open **Anaj Accounting ERP** from the Windows desktop shortcut.
2. On the Lord Ganesha screen, select the company and financial year.
3. If annual access has expired, contact support. Support will use AnyDesk to
   enter a signed key tied to the displayed installation ID.
4. Choose **Open Company**. Confirm the financial year shown in the title bar
   before entering vouchers.

Previous financial years remain editable until locked. The software warns by
showing the selected year on every screen. An administrator must provide a
reason to reopen a locked year.

## Keyboard operation

- Function keys open the entries shown in the right shortcut bar.
- Start typing a party, account or commodity. Use Up/Down to highlight and
  Enter to select.
- Enter advances to the next field. Tab/Shift+Tab move forward/back.
- Esc closes a lookup. Use the visible Exit button to close an entry window.
- A name not found in a lookup must first be created through New Party, New
  Ledger or New Commodity. This prevents duplicate spellings.

## Initial company setup

Create these ledgers before posting:

- Cash and bank accounts
- Purchases and sales accounts
- Party control/accounts
- Commission, mandi/APMC, HRDF/cess, labour/jhadhai, freight, GST and TDS
  accounts required by the company's accountant

Then create parties, commodities and effective-dated Tax & Charge Rules under
Configuration. A percentage shown in a sample bill is not automatically a
legal default. Enter only rates approved for that company, commodity, party and
effective date.

## Entries

- **Cash Book / Journal:** select debit and credit accounts, amount, date and
  narration. The software rejects an unbalanced voucher.
- **Form-J / Form-I / Sale / Purchase:** select party, commodity, posting
  accounts, bags, quantity and rate. Calculate previews effective charges.
  Save posts the document, ledger and stock in one transaction.
- **Challans / inward / outward / consignment / milling:** use the appropriate
  document type; stock is recorded through immutable movements.
- Posted records are not physically deleted. Use a reversal and enter the
  reason so the correction remains auditable.

## Bills

After saving a bill, choose a PDF destination and select Print/PDF. The A4 bill
contains company/party tax details, transport references, commodity lines,
stored expenses/taxes, totals, amount in words and signature area. PDF output
can be printed on a Windows laser or inkjet printer.

## Reports

The software provides Trial Balance, Account Ledger, Cash Book, Commodity
Balance, GST, TDS, mandi/HRDF, document registers, profit/loss and
balance-sheet datasets. Reports use stored posted values; changing a current
tax rule never changes an old bill.

## Backup and second laptop setup

1. Open **Administration / Backup** (gear menu or Configuration) and create an
   `.anajbackup` file on a safe external drive.
2. Test backups regularly. A restore can add a missing company but cannot
   overwrite a live company.
3. To work on another laptop, restore the latest backup once. Each laptop keeps
   its own standalone copy; there is no USB merge or device pairing.

**Pakki and Dasti** must remain **separate companies** with isolated databases.
Do not attempt to merge two company files manually.

Never replace or copy a live SQLite database while the application is open.
Use the built-in backup and restore actions only.

## Recovery and safety

- Do not edit database files with external tools.
- Keep multiple dated backups on separate media.
- Run the integrity check after an abnormal shutdown.
- Do not change Windows date to bypass licensing; rollback is detected.
- Preserve invoice and accountant-approved calculation examples used for
  acceptance testing.
