# Anaj ERP Implementation Summary

## Application foundation

- Windows desktop application using React, TypeScript, Python and pywebview
- Offline operation with no cloud dependency
- SQLite catalog database plus an isolated database for each company
- Windows roaming application-data storage, separated from program files
- April-March financial years with startup selection
- Editable previous years, optional year locking and audited reopening
- Original Lord Ganesha startup artwork
- Company creation, selection and financial-year selection
- Screenshot-inspired blue accounting workspace and right-side shortcut panel
- Function-key support for the displayed F2/F3/F4/F5/F6/F7/F9/F11/F12 actions
- Keyboard-first focus order and reusable autocomplete
- Up/Down selection, Enter-to-accept and Enter-to-next-field behavior

## Data safety and accounting model

- Money stored as integer paise rather than floating-point values
- Quantities and weights stored as fixed-point integers with explicit scales
- UUID identities for all master and transaction records
- Foreign-key constraints and indexed accounting queries
- Balanced double-entry voucher validation
- Immutable posted accounting events
- Reversal vouchers instead of deleting posted history
- Audit events for master creation, posting, locking, reopening and overrides
- Effective-dated calculation snapshots so old bills do not change when rates change
- SQLite WAL mode, full synchronous writes and transaction boundaries

## Masters and configuration

- Ledger/account masters
- Party masters for customers, suppliers, farmers, purchasers, commission
  agents and transporters
- Commodity, variety, HSN, quantity scale and standard bag-weight masters
- Effective-dated tax and expense rules
- Rules configurable by transaction, party and commodity
- Percentage or fixed charges
- Amount, bag, quantity or weight calculation bases
- Additive or deductive charges
- Separate ledger mapping for each configured charge
- Authorized manual overrides with a mandatory reason and audit record

## Accounting workflows

- Cash Book vouchers
- Journal vouchers
- Form-J
- Form-I debit
- Form-I credit
- Sale invoices
- Purchase invoices
- Sale and purchase memos
- Delivery and transfer challans
- Gate passes
- Inward and outward entries
- Self-purchase
- Consignment debit and credit
- Milling inward and outward
- Packing-material and warehouse-transfer document types
- Receipt/payment/contra/general voucher support through the shared ledger engine

The common document engine posts the document, voucher lines, calculated
charges and stock movement within one SQLite transaction.

## Inventory

- Immutable inventory movements
- Quantity and bag movement tracking
- Commodity and warehouse balance queries
- Purchase/inward positive movements
- Sale/outward negative movements
- Idempotency keys preventing duplicate stock movements
- Stock movements connected to their originating documents and lines

## Reports

- Trial balance
- Account ledger
- Account balance
- Cash Book receipt/payment columns
- Day book
- Commodity and warehouse stock balance
- Purchase, sale, Form-I, Form-J and challan register queries
- GST register
- TDS register
- APMC/mandi/HRDF/cess register
- Profit-and-loss and balance-sheet datasets
- Simple interest calculation
- Migration and accounting reconciliation report

## Invoice printing

- A4 PDF generation using ReportLab
- Original, Duplicate and Triplicate copy labels
- Company, party, GSTIN, PAN and address fields
- Invoice number, date, due date and transport information
- Vehicle, driver, GR and e-way bill fields
- Commodity, HSN, bags, quantity, rate and amount columns
- Expense, tax, freight and commission rows
- Grand total and amount in words
- Interest note and authorized-signature area
- Windows default-printer submission

## Annual offline licensing

- Ed25519 digitally signed annual license keys
- License tied to a permanent installation ID
- April 1 through April 30 of the following year validity model
- AnyDesk can be used to paste/install the customer key
- Vendor private key stored outside the repository
- Vendor private key protected with Windows DPAPI
- Only the public verification key is included in the customer application
- System-clock rollback detection using DPAPI-protected last-use state

## Standalone desktop operation

- Single-user offline desktop with no cloud dependency
- Pakki and Dasti isolated as separate company databases
- Backup/restore via `.anajbackup` packages only (no USB merge sync)
- Farmer credit limits with backend enforcement and override audit
- Charge-rule administration with effective-dated versioning
- Monthly TDS compliance reminder (days 1–10)

## Backup, migration and recovery

- Consistent SQLite online backups in `.anajbackup` packages
- SHA-256 backup checksums
- SQLite integrity and foreign-key checks
- Restore can add a missing company but cannot overwrite live books
- Backup restore supports initial Home Laptop setup
- Party, account and commodity CSV migration validation/import
- Dry-run migration mode
- Voucher, document, inventory and trial-balance reconciliation checks

## Build and validation completed

- React production build succeeds
- Python mypy checks succeed
- IDE diagnostics report no errors
- 15 automated tests pass
- Backend test coverage is 72%
- PyInstaller produces `dist\AnajERP\AnajERP.exe`
- Inno Setup configuration is available at `installer\AnajERP.iss`
- Source desktop launch was smoke-tested successfully

The packaged executable could not be launched on the development laptop because
its corporate group policy blocks newly generated unsigned executables. This is
an environment restriction, not a build failure.

## Required production approval

The software engine is implemented, but it must not be treated as legally
certified until a qualified Haryana mandi accountant approves:

- APMC/mandi and HRDF/cess rates
- GST and TDS applicability and effective dates
- Form-J and Form-I ledger postings
- Commission, jhadhai, labour, bagging and other expense bases
- Rounding behavior
- Printed invoice wording and layouts
- Golden examples for every supported transaction

A real commission-agent pilot should run in parallel with the existing books
before distribution to customers.