# Licensing and Voucher UI Implementation

> **Note:** Multi-device USB synchronization was removed in the standalone refactor.
> This document retains historical design notes for licensing and voucher UI only.
> Use `.anajbackup` restore for moving data between machines.

## Scope

This document describes the implemented offline subscription controls, SQLite
change tracking, two-PC USB exchange, and accounting-entry UI. It contains no
private signing key, customer token, accounting data, or device secret.

## Offline annual subscription

`backend/anaj_erp/licensing.py` verifies an Ed25519-signed token against the
public key embedded in the installed application. The private signing key stays
with the software vendor and must never be shipped to a customer.

Implemented phases:

- Before April 11: active and writable.
- April 11 through April 30: writable warning phase.
- May 1 onward: historical data remains readable, but every business write is
  rejected.
- A newly signed key may be installed while locked. A key installed late can
  start on its payment date and end on April 30 of the following year.
- Expiry never deletes, rewrites, or hides historical accounting data.

Exact warning:

> Your subscription expires on 30-Apr-[Year]. Please renew to avoid service disruption.

Exact write blocker:

> Subscription Expired. Please contact support to renew your license key.

`DesktopApi._write_call()` is the centralized write boundary. Company, master,
voucher, document, restore, import, conflict resolution and configuration
mutations pass through it. Read-only calculations and reports use `_call()`.
License installation intentionally remains available during lockdown.

### Signed JSON payload

The bytes of this canonical JSON object are URL-safe Base64 encoded and signed
with Ed25519. The displayed key is:

`base64url(canonical-json-bytes).base64url(ed25519-signature)`

```json
{
  "customer_name": "Example Grain Commission Agent",
  "installation_id": "89f2c4cc-9276-42b1-8ad6-d73e2d8c8e33",
  "license_id": "0943c0a5-a765-4a55-b8d0-49bff61b4898",
  "valid_from": "2027-05-20",
  "valid_until": "2028-04-30"
}
```

The signature covers the exact UTF-8 JSON bytes with keys sorted. Validation
requires a matching installation ID, a valid signature, ordered dates, and an
April 30 expiry.

### Clock rollback blueprint

`catalog.db` stores both a visible `last_seen_date` and a DPAPI-protected copy.
The effective last seen date is the later of the two.

```python
def check_clock(current_date):
    row = load_active_license_from_catalog()
    protected = windows_dpapi_unprotect(row.protected_state)
    last_seen = max(row.last_seen_date, protected.last_seen_date)

    if current_date < last_seen:
        raise ClockTamperException("System clock rollback detected")

    if current_date > last_seen:
        protected_state = windows_dpapi_protect({
            "license_id": row.license_id,
            "last_seen_date": current_date.isoformat(),
        })
        update_catalog_atomically(current_date, protected_state)

    if current_date > row.valid_until:
        return {"phase": "expired", "writable": False}
    if current_date >= date(row.valid_until.year, 4, 11):
        return {"phase": "warning", "writable": True}
    return {"phase": "active", "writable": True}
```

The check runs at launch, at API session access, and again inside every guarded
write. Setting the clock backward therefore cannot reopen a save operation that
was already expired. The administrator may enter a vendor-generated token in
the local activation panel during an AnyDesk support session.

## Transactional incremental synchronization

Each installation has an immutable device UUID. Synchronized records use UUIDs;
local sequence numbers order one device's outbox only and are never entity
identities.

The production schema is additive and lives in each company database:

```sql
CREATE TABLE sync_sequence (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    next_value INTEGER NOT NULL CHECK (next_value > 0)
);
INSERT OR IGNORE INTO sync_sequence(singleton_id, next_value) VALUES (1, 1);

CREATE TABLE sync_changelog (
    change_id TEXT PRIMARY KEY,
    local_sequence INTEGER NOT NULL UNIQUE,
    record_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    source_device_id TEXT NOT NULL,
    base_version INTEGER NOT NULL,
    new_version INTEGER NOT NULL,
    changed_fields_json TEXT NOT NULL DEFAULT '{}',
    transaction_context_id TEXT,
    created_at TEXT NOT NULL,
    sync_package_id TEXT
);

CREATE INDEX ix_sync_changelog_sequence
ON sync_changelog(local_sequence);
```

Sequence allocation and the originating accounting write occur in the same
SQLite transaction:

```sql
BEGIN IMMEDIATE;
SELECT next_value FROM sync_sequence WHERE singleton_id = 1;
UPDATE sync_sequence SET next_value = next_value + 1 WHERE singleton_id = 1;
-- Perform the master, voucher, document, stock, or financial-year write.
INSERT INTO sync_changelog(
    change_id, local_sequence, record_id, entity_type, operation,
    source_device_id, base_version, new_version, changed_fields_json,
    transaction_context_id, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
COMMIT;
```

If any statement fails, SQLite rolls back both the business row and outbox row,
including the sequence increment. Incremental export is:

```sql
SELECT *
FROM sync_changelog
WHERE local_sequence > ?
ORDER BY local_sequence;
```

After a package is safely created, exported rows receive its package UUID:

```sql
UPDATE sync_changelog
SET sync_package_id = ?
WHERE local_sequence BETWEEN ? AND ?;
```

The implementation uses application-level transactional outbox capture rather
than generic SQLite triggers. A trigger cannot reliably supply the current
device identity, transaction context, canonical aggregate snapshot, or
accounting operation semantics. All writes are therefore routed through domain
services, and `track_change()` is called on the same connection before commit.
Database constraints still enforce sequence uniqueness and entity integrity.

### USB export and import

1. Verify the paired target device and select only changes after that peer's
   last acknowledged sequence.
2. Build a manifest and canonical record snapshots.
3. Include related voucher/document lines, inventory movements and attachments.
4. Encrypt for the paired device, sign with the source device key, checksum the
   container, and write one `.anajsync` file.
5. On import, verify checksum, signature, target, schema and package UUID.
6. Use a savepoint per aggregate. Apply exact UUID inserts idempotently.
7. Merge non-overlapping master fields; isolate divergent financial mutations.
8. Treat unique number collisions as conflicts and roll back the whole
   aggregate savepoint, preventing partial child rows.
9. Record imported package UUIDs. Importing the same file again makes zero
   accounting changes.
10. Conflict decisions create a new tracked revision so the decision returns to
    the other computer in the next exchange.

Posted transactions are append-oriented. Corrections use reversals or
adjustments; finalized years can be locked and that lock state also
synchronizes.

## Accounting UI implemented

- Company table and April-to-March labels such as `2026-2027`.
- Form-J, Form-I Debit/Sale Bill and Form-I Credit connected line grids.
- Integer bag stepping; quantity uses `((bags × pack) + extra) / 100`.
- Connected Expense / `% or Unit` / Amount table with configured percentage,
  per-bag, quantity, weight, add and deduct rules.
- Compact Journal grid with Particulars, Amount (Cr.), Amount (Dr.) and Remarks.
- Cash Book with Cash in Hand plus side-by-side Receipt and Payment tables.
- Searchable master inputs, arrow-key selection and Enter-to-next-field.
- Enter on the final editable cell appends and focuses the next grid row.
- Calculate, Print, Save and Exit actions on statutory document forms.
- Successful writes and print requests show `Data has been Successfully Saved`.
- Physical printing uses a generated temporary PDF and the Windows print path;
  saving a named PDF remains available on general invoice forms.

## Verification boundary

Automated tests cover license dates, expiry write rejection, late renewal,
clock rollback, transactional monotonic sequences, encrypted duplicate import,
master exchange and financial-year lock exchange. Before production rollout,
an accountant must approve real mandi rates, tax treatment, rounding, print
formats and statutory wording for each target state and market committee.
