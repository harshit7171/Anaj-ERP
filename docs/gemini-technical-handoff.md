# Anaj Accounting ERP — Technical Handoff for External Review

## 1. Purpose of this document

This document describes the Anaj Accounting ERP implementation currently built
in `C:\A_Software`. It is intended to be given to Gemini or another technical
reviewer so they can understand the system and recommend changes.

The application is an offline Windows accounting ERP for grain-market
commission agents. It is keyboard-first and designed for operators who prefer
function keys, autocomplete, arrow keys and Enter instead of frequent mouse
usage.

This document contains architecture and behavior only. It intentionally does
not contain:

- The vendor's private license-signing key
- Customer license tokens
- Customer accounting data
- Device private keys
- Production credentials

## 2. Current implementation status

The project is a working implementation rather than only a UI prototype.
Implemented areas include:

- Windows desktop shell
- React accounting interface
- SQLite storage
- Company and financial-year selection
- Master records
- Double-entry vouchers
- Form-J
- Form-I Debit
- Form-I Credit
- Sale and purchase workflows
- Stock movements
- Configurable mandi expenses and taxes
- Reports
- PDF invoice generation
- Offline annual licensing
- Encrypted two-device USB synchronization
- Backup, restore and migration tools
- PyInstaller and Inno Setup packaging configuration

Current automated validation:

- 18 automated tests pass
- TypeScript production build passes
- Python mypy validation passes
- IDE diagnostics report no errors in the edited files

The software is not yet legally or commercially certified. Tax rates, mandi
rules, ledger treatment, rounding and printed formats must be approved by a
qualified accountant and tested with real commission-agent books.

## 3. Technology stack

### Desktop application

- Python 3.11-compatible backend
- `pywebview` for the native Windows application window
- React 19
- TypeScript
- Vite
- CSS

### Storage and accounting

- SQLite
- Integer paise for money
- Fixed-point scaled integers for quantities and weights
- UUID identifiers
- SQLite WAL journaling
- Full synchronous writes
- Foreign-key enforcement
- Explicit database transactions

### Security and packaging

- `cryptography` Python package
- Ed25519 signatures
- X25519 key agreement
- HKDF key derivation
- AES-256-GCM encryption
- Windows DPAPI for local secret protection
- ReportLab for PDF invoices
- PyInstaller for Windows application packaging
- Inno Setup configuration for the installer

## 4. High-level architecture

The application is divided into these layers:

1. React/TypeScript renders the desktop interface.
2. The UI calls the Python bridge exposed by pywebview.
3. The Python API validates context and delegates to domain services.
4. Accounting and document services perform calculations and postings.
5. SQLite commits business data, ledger entries, stock movements, audit rows
   and synchronization changes within controlled transactions.
6. Reporting and printing services read stored posted values.

Important source files:

- `frontend/src/App.tsx` — startup, company/year selection, menus and shortcuts
- `frontend/src/EntryWindow.tsx` — voucher, Form-J, Form-I and invoice screens
- `frontend/src/Autocomplete.tsx` — keyboard-first master lookup
- `frontend/src/styles.css` — desktop and accounting-form styling
- `backend/anaj_erp/api.py` — pywebview API boundary
- `backend/anaj_erp/database.py` — SQLite schemas and additive migrations
- `backend/anaj_erp/accounting.py` — masters and double-entry vouchers
- `backend/anaj_erp/documents.py` — invoices, mandi forms, charges and stock
- `backend/anaj_erp/reports.py` — accounting, tax and inventory reports
- `backend/anaj_erp/printing.py` — PDF and Windows print support
- `backend/anaj_erp/licensing.py` — customer-side offline license verification
- `backend/anaj_erp/sync.py` — encrypted Office/Home synchronization
- `backend/anaj_erp/backup.py` — backup and restore packages
- `backend/anaj_erp/maintenance.py` — import and reconciliation
- `tools/license_admin.py` — vendor-only license issuance tool

## 5. Windows data storage

Program files and customer data are deliberately separated.

The default data location is obtained through `platformdirs.user_data_path`
using the application name `AnajERP` with roaming enabled. On Windows this is
normally under the current user's roaming application-data folder.

The storage layout contains:

- `catalog.db` — installation-wide configuration
- `companies\` — one isolated SQLite database per company
- Company databases named using the company UUID

The executable or installer may be replaced without deleting accounting data.
An upgrade must preserve the Windows user's AnajERP data directory.

## 6. SQLite catalog database

`catalog.db` stores installation-level information:

- `installation`
  - Permanent random installation UUID
  - Created once on first initialization
- `device_identity`
  - Permanent device UUID
  - Device name
  - Ed25519 signing public key
  - X25519 encryption public key
  - DPAPI-protected private-key material
- `paired_device`
  - The one permitted Office/Home peer
  - Peer signing and encryption public keys
- `license_state`
  - Installed signed license payload
  - Signature
  - Validity dates
  - Last-seen date
  - DPAPI-protected anti-clock-rollback state
- `company_catalog`
  - Company UUID
  - Display name
  - Company database filename

The catalog database is local to each Windows installation. Office and Home
devices therefore have different installation IDs, device IDs and license
keys.

## 7. Per-company SQLite database

Each company has an isolated database containing:

- `schema_version`
- `company`
- `financial_year`
- `account`
- `party`
- `commodity`
- `charge_rule`
- `voucher`
- `voucher_line`
- `audit_event`
- `numbering_series`
- `document`
- `document_line`
- `document_charge`
- `inventory_movement`
- `sync_changelog`
- `sync_package_receipt`
- `sync_peer_cursor`
- `sync_conflict`

### Important storage rules

- Synchronized identities use UUIDs.
- Posted voucher and document records are treated as accounting events.
- Posted accounting history is corrected by reversal, not physical deletion.
- Money is stored as integer paise.
- Quantities are stored as integer values plus an explicit decimal scale.
- Calculated charges are saved with the document.
- Old invoices do not recalculate when current rates change.
- Company/year access is validated before posting.
- Locked financial years reject normal posting.

### SQLite safety configuration

Every managed connection enables:

- `PRAGMA foreign_keys = ON`
- `PRAGMA journal_mode = WAL`
- `PRAGMA synchronous = FULL`
- A busy timeout
- An explicit immediate transaction

Failures roll back the active transaction.

## 8. Financial-year behavior

- Financial years run from April 1 through March 31.
- UI labels use the complete range, for example `2026-2027`.
- Data remains separated and queryable by financial-year ID.
- Previous years remain editable until explicitly locked.
- Reopening a locked year requires an audited reason.
- Document dates are checked against the selected financial year.

## 9. Master data

Implemented masters include:

- Ledger accounts
- Customers
- Suppliers
- Farmers
- Purchasers
- Commission agents
- Transporters
- Commodities
- Commodity varieties
- HSN codes
- Standard bag weights
- Configurable tax and charge rules

Party lookup can return address, GSTIN, linked account and related/father/group
name. The React autocomplete supports:

- Prefix and contains search
- Up/Down selection
- Enter to accept
- Escape to close
- Automatic movement to the next field

## 10. Accounting model

### Double-entry ledger

Every posted financial voucher must balance:

- Total debit equals total credit.
- Voucher lines reference ledger accounts.
- Posted entries are not silently edited or deleted.
- Reversal vouchers preserve the correction trail.

### Document posting transaction

A financial document can write all of the following within one SQLite
transaction:

- Document header
- Document lines
- Stored expense/tax rows
- Main accounting voucher
- Voucher lines
- Inventory movements
- Advance-cash receipt voucher when applicable
- Audit event
- Synchronization changelog event

If one operation fails, the transaction is rolled back.

### Calculation model

- Gross line amount = quantity × rate
- Quantity in quintals = `((bags × pack weight) + loose weight) / 100`
- Non-tax mandi expenses are calculated first.
- Freight may be added or deducted.
- GST rules calculate on the taxable value after non-tax expenses and freight.
- Bonus direction depends on the document workflow.
- Final calculation values are stored with the document.

Rounding uses decimal arithmetic with half-up conversion to integer paise.

## 11. ERP screens and workflows

### Startup and desktop

- Lord Ganesha startup screen
- Company table
- Financial-year selector
- Create company and year
- Annual-key activation
- Blue legacy-style accounting workspace
- Right-side function-key buttons
- Top Entry menu
- Desktop shortcut through the installer

### Keyboard shortcuts

Implemented navigation includes:

- F2 Cash Book
- F3 Journal
- F4 Form-J
- F5 Form-I Debit
- F6 New Commodity
- F7 New Ledger
- F9 Account Balance
- F11 Form-I Credit
- F12 Transfer Challan
- Ctrl+N New Party
- Ctrl+S Sale Invoice
- Ctrl+P Purchase Invoice
- Ctrl+F Self Purchase on Form-J

### Voucher/document workflows

- Cash Book
- Journal
- Accounting Voucher
- Debit Note
- Credit Note
- Form-J
- Form-I Debit
- Form-I Credit
- Sale Invoice
- Purchase Invoice
- Sale Memo
- Purchase Memo
- Delivery Challan
- Transfer Challan
- Gate Pass
- Inward
- Outward
- Consignment Debit/Credit
- Milling Inward/Outward
- Packing Material Transfer
- Warehouse Transfer

Some less-specialized document types currently reuse the common document
engine and may need dedicated UI screens after business review.

## 12. Form-J implementation

The dedicated Form-J workflow currently includes:

- Farmer selection
- Father/group information through party lookup
- Automatic `J-` numbering
- Date and due date
- Multiple Dheri rows
- Commodity
- Purchaser
- Gate-pass number
- Bags
- Pack weight
- Loose/extra weight
- Calculated quintal quantity
- Rate per quintal
- Calculated amount
- Add/remove expense rules
- Total amount
- Total expenses
- Bonus
- Net amount
- Purchase account
- Farmer account
- Commodity-transfer account
- Gate-pass flag
- Ctrl+F self-purchase mode

The screen uses compact table-style cells. Bags increment by whole units.
Pack, loose weight and rate accept decimal keyboard input without number-field
spinner behavior.

## 13. Sale Bill / Form-I Debit implementation

Sale Invoice and Form-I Debit use the detailed outbound sale-bill screen:

- Buyer party
- Auto-filled address
- Auto-filled GSTIN
- Invoice number
- Date and due date
- Vehicle number
- GR/Bilty number and date
- Dispatch time
- e-Way Bill number
- Delivery location
- Multiple commodity/Dheri lines
- Original source/Dheri reference number
- Source commission agent
- Bags, pack, extra, quantity, rate and amount
- Grid totals
- Mandi expenses
- SGST/CGST
- Freight Add/Deduct selector
- Advance cash paid
- Balance amount
- Insurance/remarks
- Packing-material-transfer flag
- Stock-sale flag
- Multi-tax flag
- Sale and party posting accounts
- Cash account for advance receipt

Advance cash creates a linked receipt voucher in the same transaction:

- Debit cash
- Credit buyer/party account

The save operation shows a blocking Windows-style confirmation dialog:

`Data has been Successfully Saved`

## 14. Form-I Credit implementation

Form-I Credit has a dedicated inbound purchase-credit screen:

- Commission-agent/supplier selection
- Original Form-I reference number
- Header commodity
- Automatic `IP-` numbering
- Date and due date
- Multiple inbound Dheri rows
- Commodity
- Whole-number bags
- Pack weight
- Loose/extra quantity
- Calculated quintal quantity
- Purchase rate
- Gross amount
- Commodity balance
- Grid totals
- Inbound expense list
- SGST/CGST area
- Bonus deduction
- Net purchase liability
- Purchase account
- Party account
- Save confirmation dialog

Default editable inbound calculations currently seeded for Form-I Credit:

- Dami: 2.50% of gross amount
- Labour: ₹2.70 per bag
- Auction: 0.10% of gross amount
- Association: 0.02% of gross amount

For the reference example:

- Gross amount: ₹36,680.00
- Dami: ₹917.00
- Labour: ₹151.20
- Auction: ₹36.68
- Association: ₹7.34
- Total expenses: ₹1,112.22
- Total before bonus/tax: ₹37,792.22

Bonus is deductive for this workflow. Inventory increases when Form-I Credit is
posted.

## 15. Sale levy defaults

The database migration installs editable baseline rules for Sale Invoice and
Form-I Debit:

- Dami: 2.50% of amount
- Labour: ₹2.70 per bag
- Auction: 0.10% of amount
- Market Fees: 2.00% of amount
- HRDF: 2.00% of amount
- Association: 0.02% of amount
- SGST: 2.50% of amount after non-tax charges
- CGST: 2.50% of amount after non-tax charges

Associated ledgers are also created if missing. User-created newer
effective-dated rules take precedence.

These values came from reference screenshots. They must remain configurable
and must be approved for each jurisdiction, commodity, party and effective
date before production use.

## 16. Inventory

Inventory is based on immutable movement rows:

- Purchase and inward documents add stock.
- Sale and outward documents reduce stock.
- Quantity and bag totals are recorded.
- Movements reference their source document and document line.
- Idempotency keys prevent duplicate movements for the same source line.
- Commodity and warehouse balances are derived from movement totals.

The application does not store only a manually edited current-stock number.

## 17. Reports

Implemented report services include:

- Trial Balance
- Account Ledger
- Account Balance
- Cash Book
- Day Book
- Commodity Balance
- Warehouse Stock Balance
- Purchase Register
- Sale Register
- Form-I Register
- Form-J Register
- Challan Register
- GST Register
- TDS Register
- Mandi/APMC/HRDF/Cess Register
- Profit and Loss dataset
- Balance Sheet dataset
- Simple Interest calculation
- Reconciliation report

Some datasets may still require dedicated screenshot-matched presentation
screens.

## 18. Printing

The invoice printer supports:

- A4 PDF generation
- Original, Duplicate and Triplicate labels
- Company and party details
- GSTIN/PAN/address
- Invoice and due dates
- Transport references
- Commodity lines
- Bags, quantity, rate and amount
- Stored expenses and taxes
- Freight and commission rows
- Grand total
- Amount in words
- Signature area
- Submission to the Windows default printer

Printed layouts still require exact comparison with approved customer samples.

## 19. Annual offline renewal-key system

### Goal

The application works without internet access. A customer receives access for
one annual cycle:

- Valid from April 1 of the selected start year
- Valid through April 30 of the following year

Example:

- Start year: 2026
- Valid from: April 1, 2026
- Valid until: April 30, 2027

### Installation identity

On first initialization, the application creates a random installation UUID.
It does not use the Windows computer name as the license identity.

Each laptop has its own installation ID. Therefore:

- Office PC license does not activate the Home Laptop.
- Home Laptop requires its own signed token.
- Reinstalling while deleting all application data produces a new identity.
- A controlled support process is required for genuine device replacement.

### Vendor signing keys

The vendor-only tool uses Ed25519:

- Private key signs customer license payloads.
- Public key is included in the customer application.
- Private key is not included in the installer.
- Private key is stored outside the repository.
- Private key bytes are protected for the vendor Windows user with DPAPI.
- Key initialization refuses to overwrite existing key files.

Vendor key initialization:

```powershell
cd C:\A_Software
py -3.14 tools\license_admin.py init `
  --public "resources\license_public_key.pem"
```

The default protected private key location is in the vendor user's application
data under `AnajERPVendor`.

### Issuing a customer renewal key

Run only on the protected vendor/support laptop:

```powershell
cd C:\A_Software
py -3.14 tools\license_admin.py issue `
  --installation-id "<CUSTOMER-INSTALLATION-ID>" `
  --customer "<CUSTOMER OR FIRM NAME>" `
  --start-year 2026 `
  --output "customer-2026.license"
```

The token contains:

- Unique license UUID
- Installation UUID
- Customer name
- Valid-from date
- Valid-until date
- Issue date
- Ed25519 signature

The token format is:

```text
base64url(canonical JSON payload).base64url(Ed25519 signature)
```

### Renewal procedure

1. Customer opens the startup screen.
2. Customer/support copies the displayed Installation ID.
3. Customer pays through the agreed offline process.
4. Vendor issues a token for that exact Installation ID and start year.
5. Support connects through AnyDesk or provides the token securely.
6. Token is pasted into the annual-key field.
7. Customer selects Activate.
8. The application verifies the signature and installation binding locally.
9. The new license revokes the previously active local license row.
10. The application stores the signed payload and validity state in
    `catalog.db`.

No cloud activation call is required.

### Customer-side verification

The application checks:

- Token has two valid segments.
- Payload is valid JSON.
- Ed25519 signature matches the embedded vendor public key.
- Installation ID matches this installation.
- Validity dates are valid.
- End date is April 30.
- Current date is inside the licensed period.

### Clock-rollback protection

The last successful use date is stored twice:

- In the catalog database
- In a DPAPI-protected state blob

The application uses the later value. If the current date is earlier than the
recorded last-use date, license validation fails with a clock-rollback reason.

### Security boundaries and limitations

- The private signing key must be backed up securely; losing it prevents
  issuing compatible future tokens.
- Public-key verification prevents customers from generating valid tokens
  without the private key.
- DPAPI protects secrets for the current Windows user but is not a substitute
  for full-disk encryption.
- A determined local administrator can modify application binaries. Production
  builds should therefore be code-signed and hardened.
- Fully offline licensing cannot provide real-time revocation.
- The current anti-rollback check detects dates earlier than the last recorded
  use; it is not secure hardware time.

## 20. Office PC and Home Laptop synchronization

### Goal

Both devices remain independently writable. Changes are exchanged through a
pen drive without copying or replacing live SQLite databases.

Exactly one peer is permitted:

- Office PC
- Home Laptop

### Device identity and keys

Each device creates:

- Permanent random device UUID
- Ed25519 signing key pair
- X25519 encryption key pair

Private keys are stored in `catalog.db` only after being protected with Windows
DPAPI. Public keys are exported for pairing.

### Initial Home Laptop setup

1. Install and license both laptops independently.
2. Create a company on the Office PC.
3. Create an `.anajbackup` on the Office PC.
4. Restore it as a new company on the Home Laptop.
5. Export pairing data from both devices.
6. Import each device's pairing file on the other device.
7. Confirm customer/device fingerprints during setup.

### Pairing file

The `.anajpair` file contains only public identity data:

- Format and version
- Device UUID
- Device name
- Ed25519 public key
- X25519 public key
- Creation timestamp
- SHA-256 fingerprint

Import rejects:

- Pairing with self
- Invalid key lengths
- Invalid fingerprint
- A second unrelated peer when one peer is already configured

The pairing file is explicitly trusted by the operator. Its self-contained
fingerprint protects integrity/corruption but does not by itself prove the
real-world identity of the other laptop. Fingerprints should be compared
during setup.

### Change capture

Business services write a `sync_changelog` record in the same transaction as
tracked business changes.

The changelog includes:

- Change UUID
- Local sequence
- Record UUID
- Entity type
- Operation
- Source device UUID
- Base version
- New version
- Changed fields JSON
- Transaction context UUID
- Timestamp

### Data classifications

Versioned mutable masters:

- Accounts
- Parties
- Commodities
- Charge rules

Immutable/event-oriented accounting data:

- Vouchers
- Voucher lines
- Documents
- Document lines
- Document charges
- Inventory movements

### Export

Export reads changes after the peer's acknowledged sequence and creates
snapshots for the affected records.

The package is:

- Bound to one target device
- Signed by the source device using Ed25519
- Encrypted using a key derived from X25519 and HKDF
- Encrypted with AES-256-GCM
- Written with the `.anajsync` extension

The package includes logical change and snapshot data, not a copied live
company database.

The current maximum accepted package size is 250 MB.

### Import verification

Before applying changes, import verifies:

- File-size limit
- Package structure
- Target device ID
- Source paired-device ID
- Ed25519 signature
- AES-GCM authentication/decryption
- Package schema version
- Company/package metadata
- Package receipt history

The import is then applied in a transaction.

### Idempotency

Imported package IDs are recorded in `sync_package_receipt`.

If the same package is imported again:

- No accounting rows are duplicated.
- No stock movement is duplicated.
- The operation returns as an already processed package.

### Master conflicts

Master changes use base/new versions.

If the incoming baseline matches the host version, the change can be applied.
If host and incoming versions diverge, a conflict row is created.

Resolution options include:

- Keep Host
- Keep Package
- Manual merged values

The resolution creates a new local revision so it can travel back to the peer.

### Posted financial conflicts

Posted vouchers and documents are not overwritten with arbitrary remote
values. If an accounting correction is needed, the workflow should keep the
posted event and use reversal/replacement entries.

### Daily round trip

Office to Home:

1. Export `.anajsync` from Office.
2. Copy through the pen drive.
3. Import on Home.
4. Resolve conflicts if shown.

Home to Office:

1. Export a new `.anajsync` from Home.
2. Import on Office.
3. Resolve conflicts.
4. Export a later return package so acknowledgements and resolution revisions
   travel back.

### Important sync limitations for review

- Sync correctness depends on all business writes going through tracked
  services. Direct external SQL edits must never be used.
- The pairing trust ceremony should be reviewed for stronger operator
  verification.
- Schema migration compatibility is currently versioned but should be tested
  across real software upgrades.
- Large attachment/document synchronization is not currently described as a
  completed production feature.
- Device replacement/unpairing requires a controlled support workflow.
- Conflict UI and long multi-round synchronization should receive pilot
  testing with realistic data volumes.

## 21. Backup and recovery

Backup is separate from synchronization.

Implemented backup behavior:

- Uses SQLite's consistent online backup mechanism
- Produces `.anajbackup`
- Adds SHA-256 integrity information
- Runs SQLite integrity checks
- Runs foreign-key checks
- Restore can add a missing company
- Restore refuses to overwrite an existing live company

Recommended operation:

- Daily backup
- At least three recent copies
- One copy on separate media
- Periodic test restore

Never use raw database file copying as the Office/Home synchronization method.

## 22. Build and installation

React build:

```powershell
cd C:\A_Software
npm run build
```

Windows portable build:

```powershell
py -3.14 -m PyInstaller AnajERP.spec --clean --noconfirm
```

Portable output:

```text
C:\A_Software\dist\AnajERP\
```

The Inno Setup definition is:

```text
C:\A_Software\installer\AnajERP.iss
```

Customer laptops do not need Python, Node.js, npm or Cursor after installing
the packaged application.

Production executables and installers should be code-signed.

## 23. Areas Gemini should review

Please review the architecture and propose changes without removing the
offline-first requirement or accounting audit trail.

Priority review questions:

1. Are Form-J, Form-I Debit and Form-I Credit debit/credit postings correct for
   Haryana commission-agent accounting?
2. Should seeded reference rates be enabled automatically, or should they
   require explicit accountant approval before first use?
3. Are GST bases, freight treatment, bonus direction and rounding correct?
4. Should separate control accounts be mandatory for every expense/tax?
5. Is the annual licensing model commercially adequate for 8,000–9,000
   independent customers?
6. How should genuine laptop replacement and license reissue be controlled?
7. What additional protection is useful without requiring cloud activation?
8. Is the pairing trust ceremony strong enough for non-technical users?
9. Which sync tables or business events are not yet fully captured?
10. How should schema-version upgrades be coordinated between Office and Home?
11. What load/performance tests are needed for large companies and many years?
12. Which reports are legally required for Haryana mandi operators?
13. What invoice fields and print wording need statutory validation?
14. Which dedicated screens are still needed instead of the common document
    form?
15. What backup retention and disaster-recovery policy should be shipped?

## 24. Rules for future changes

Any proposed change should preserve these invariants:

- Offline operation must remain possible.
- Money must not be stored as binary floating point.
- Posted vouchers must remain balanced.
- Posted accounting history must not be physically deleted.
- Corrections must be auditable.
- Inventory movement duplication must be prevented.
- Sync imports must remain idempotent.
- Live SQLite databases must not be replaced during synchronization.
- Private signing keys must never enter the customer build or repository.
- Existing customer databases must be upgraded through additive, tested
  migrations.
- Existing business logic must not be replaced without equivalent regression
  tests.
- Tax and mandi logic must remain effective-dated and configurable.

## 25. Recommended prompt to give Gemini

Use this prompt together with this document:

> Review this offline Anaj Accounting ERP implementation as a senior Windows
> desktop, SQLite, accounting, security and distributed-synchronization
> architect. Identify correctness gaps, security risks, missing mandi
> workflows, licensing weaknesses, sync edge cases, UI usability issues and
> production-readiness problems. Do not recommend converting it to a
> cloud-only system. Preserve offline operation, double-entry accounting,
> immutable posted history, UUID-based idempotent USB synchronization and
> configurable effective-dated tax rules. Separate your response into:
> critical defects, accounting questions requiring professional approval,
> security improvements, synchronization improvements, database improvements,
> UI/workflow improvements, testing strategy and a prioritized implementation
> roadmap. Clearly distinguish verified facts from assumptions.

