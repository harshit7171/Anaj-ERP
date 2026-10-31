"""SQLite catalog and company database lifecycle.

The catalog stores installation-wide company discovery. Each company receives
an isolated SQLite database containing all of its financial years.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path

from .data_paths import resolve_data_dir
from .domain import FinancialYear
from .errors import DatabaseError
from .errors import ValidationError

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 11


def configure_sqlite_connection(connection: sqlite3.Connection) -> None:
    """Apply standard SQLite pragmas for every application connection."""
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")

CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS installation (
    installation_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_identity (
    device_id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    signing_public_key BLOB,
    encryption_public_key BLOB,
    protected_private_keys BLOB,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS license_state (
    license_id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    signed_payload TEXT NOT NULL,
    signature TEXT NOT NULL,
    installed_at TEXT NOT NULL,
    last_seen_date TEXT NOT NULL,
    protected_state BLOB,
    is_revoked INTEGER NOT NULL DEFAULT 0 CHECK (is_revoked IN (0, 1)),
    FOREIGN KEY (installation_id) REFERENCES installation(installation_id)
);

CREATE TABLE IF NOT EXISTS company_catalog (
    company_id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE,
    database_filename TEXT NOT NULL UNIQUE,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_company_catalog_active_name
ON company_catalog(name) WHERE is_deleted = 0;

CREATE TABLE IF NOT EXISTS app_user (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'munim', 'operator', 'clerk', 'readonly')),
    can_view_kachi INTEGER NOT NULL DEFAULT 0 CHECK (can_view_kachi IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_session (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES app_user(user_id)
);
"""

COMPANY_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS company (
    company_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    legal_name TEXT,
    address TEXT,
    gstin TEXT,
    pan TEXT,
    state_code TEXT NOT NULL DEFAULT '06',
    phone TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS financial_year (
    financial_year_id TEXT PRIMARY KEY,
    start_year INTEGER NOT NULL UNIQUE CHECK (start_year BETWEEN 2000 AND 9998),
    starts_on TEXT NOT NULL,
    ends_on TEXT NOT NULL,
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
    lock_reason TEXT,
    locked_at TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account (
    account_id TEXT PRIMARY KEY,
    financial_year_id TEXT,
    name TEXT NOT NULL COLLATE NOCASE,
    account_type TEXT NOT NULL,
    parent_account_id TEXT,
    opening_debit_paise INTEGER NOT NULL DEFAULT 0 CHECK (opening_debit_paise >= 0),
    opening_credit_paise INTEGER NOT NULL DEFAULT 0 CHECK (opening_credit_paise >= 0),
    version INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id),
    FOREIGN KEY (parent_account_id) REFERENCES account(account_id),
    CHECK (opening_debit_paise = 0 OR opening_credit_paise = 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_account_active_name_year
ON account(COALESCE(financial_year_id, ''), name) WHERE is_deleted = 0;

CREATE TABLE IF NOT EXISTS party (
    party_id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE,
    related_name TEXT,
    father_name TEXT,
    agricultural_group TEXT,
    village_name TEXT,
    party_type TEXT NOT NULL,
    account_id TEXT,
    credit_limit_paise INTEGER NOT NULL DEFAULT 0 CHECK (credit_limit_paise >= 0),
    address TEXT,
    city TEXT,
    state_code TEXT NOT NULL DEFAULT '06',
    gstin TEXT,
    pan TEXT,
    phone TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES account(account_id)
);

CREATE INDEX IF NOT EXISTS ix_party_name ON party(name);
CREATE INDEX IF NOT EXISTS ix_party_type ON party(party_type, is_deleted);

CREATE TABLE IF NOT EXISTS commodity (
    commodity_id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE,
    variety TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
    hsn_code TEXT,
    quantity_scale INTEGER NOT NULL DEFAULT 3 CHECK (quantity_scale BETWEEN 0 AND 6),
    standard_bag_weight_scaled INTEGER,
    version INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_commodity_active_name
ON commodity(name, variety) WHERE is_deleted = 0;

CREATE TABLE IF NOT EXISTS charge_rule (
    charge_rule_id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    commodity_id TEXT,
    party_id TEXT,
    basis TEXT NOT NULL CHECK (basis IN ('amount', 'bag', 'quantity', 'weight')),
    mode TEXT NOT NULL CHECK (mode IN ('percentage', 'fixed')),
    rate_decimal TEXT NOT NULL,
    direction TEXT NOT NULL DEFAULT 'add' CHECK (direction IN ('add', 'deduct')),
    is_tax INTEGER NOT NULL DEFAULT 0 CHECK (is_tax IN (0, 1)),
    ledger_account_id TEXT,
    priority INTEGER NOT NULL DEFAULT 100,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (commodity_id) REFERENCES commodity(commodity_id),
    FOREIGN KEY (party_id) REFERENCES party(party_id),
    FOREIGN KEY (ledger_account_id) REFERENCES account(account_id),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS ix_charge_rule_resolution
ON charge_rule(transaction_type, effective_from, effective_to, priority);

CREATE TABLE IF NOT EXISTS voucher (
    voucher_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    voucher_type TEXT NOT NULL,
    voucher_number TEXT NOT NULL,
    voucher_date TEXT NOT NULL,
    narration TEXT,
    entry_metadata_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted', 'reversed')),
    reversal_of_voucher_id TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id),
    FOREIGN KEY (reversal_of_voucher_id) REFERENCES voucher(voucher_id),
    UNIQUE (financial_year_id, voucher_type, voucher_number)
);

CREATE TABLE IF NOT EXISTS voucher_line (
    voucher_line_id TEXT PRIMARY KEY,
    voucher_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    debit_paise INTEGER NOT NULL DEFAULT 0 CHECK (debit_paise >= 0),
    credit_paise INTEGER NOT NULL DEFAULT 0 CHECK (credit_paise >= 0),
    narration TEXT,
    line_metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (voucher_id) REFERENCES voucher(voucher_id) ON DELETE RESTRICT,
    FOREIGN KEY (account_id) REFERENCES account(account_id),
    UNIQUE (voucher_id, line_number),
    CHECK ((debit_paise > 0 AND credit_paise = 0)
        OR (credit_paise > 0 AND debit_paise = 0))
);

CREATE INDEX IF NOT EXISTS ix_voucher_date ON voucher(financial_year_id, voucher_date);
CREATE INDEX IF NOT EXISTS ix_voucher_line_account ON voucher_line(account_id, voucher_id);

CREATE TABLE IF NOT EXISTS audit_event (
    audit_event_id TEXT PRIMARY KEY,
    financial_year_id TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id)
);

CREATE INDEX IF NOT EXISTS ix_audit_entity
ON audit_event(entity_type, entity_id, occurred_at);

CREATE TABLE IF NOT EXISTS numbering_series (
    financial_year_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    prefix TEXT NOT NULL,
    next_number INTEGER NOT NULL DEFAULT 1 CHECK (next_number > 0),
    PRIMARY KEY (financial_year_id, document_type),
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id)
);

CREATE TABLE IF NOT EXISTS document (
    document_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_number TEXT NOT NULL,
    document_date TEXT NOT NULL,
    party_id TEXT,
    ship_to_party_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'posted', 'reversed')),
    reference_number TEXT,
    due_date TEXT,
    vehicle_number TEXT,
    driver_name TEXT,
    gr_number TEXT,
    eway_bill_number TEXT,
    po_number TEXT,
    from_place TEXT,
    to_place TEXT,
    remarks TEXT,
    dispatch_time TEXT,
    gr_date TEXT,
    freight_paise INTEGER NOT NULL DEFAULT 0,
    freight_direction TEXT NOT NULL DEFAULT 'add',
    advance_cash_paise INTEGER NOT NULL DEFAULT 0,
    balance_paise INTEGER NOT NULL DEFAULT 0,
    insurance_number TEXT,
    packing_material_transfer INTEGER NOT NULL DEFAULT 0,
    stock_sale INTEGER NOT NULL DEFAULT 0,
    multi_tax INTEGER NOT NULL DEFAULT 0,
    cash_account_id TEXT,
    advance_receipt_voucher_id TEXT,
    commodity_transfer_account_id TEXT,
    gate_pass_required INTEGER NOT NULL DEFAULT 0
        CHECK (gate_pass_required IN (0, 1)),
    self_purchase INTEGER NOT NULL DEFAULT 0
        CHECK (self_purchase IN (0, 1)),
    subtotal_paise INTEGER NOT NULL DEFAULT 0,
    total_charges_paise INTEGER NOT NULL DEFAULT 0,
    total_tax_paise INTEGER NOT NULL DEFAULT 0,
    grand_total_paise INTEGER NOT NULL DEFAULT 0,
    calculation_snapshot_json TEXT NOT NULL DEFAULT '{}',
    header_metadata_json TEXT NOT NULL DEFAULT '{}',
    posted_voucher_id TEXT,
    reversal_of_document_id TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id),
    FOREIGN KEY (party_id) REFERENCES party(party_id),
    FOREIGN KEY (ship_to_party_id) REFERENCES party(party_id),
    FOREIGN KEY (cash_account_id) REFERENCES account(account_id),
    FOREIGN KEY (advance_receipt_voucher_id) REFERENCES voucher(voucher_id),
    FOREIGN KEY (commodity_transfer_account_id) REFERENCES account(account_id),
    FOREIGN KEY (posted_voucher_id) REFERENCES voucher(voucher_id),
    FOREIGN KEY (reversal_of_document_id) REFERENCES document(document_id),
    UNIQUE (financial_year_id, document_type, document_number)
);

CREATE INDEX IF NOT EXISTS ix_document_date
ON document(financial_year_id, document_type, document_date);

CREATE TABLE IF NOT EXISTS document_line (
    document_line_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    commodity_id TEXT NOT NULL,
    purchaser_party_id TEXT,
    source_party_id TEXT,
    source_reference_number TEXT,
    gate_pass_number TEXT,
    description TEXT NOT NULL,
    hsn_code TEXT,
    bags_scaled INTEGER NOT NULL DEFAULT 0,
    bag_scale INTEGER NOT NULL DEFAULT 0 CHECK (bag_scale BETWEEN 0 AND 3),
    packing_weight_scaled INTEGER NOT NULL DEFAULT 0,
    loose_quantity_scaled INTEGER NOT NULL DEFAULT 0,
    quantity_scaled INTEGER NOT NULL,
    quantity_scale INTEGER NOT NULL CHECK (quantity_scale BETWEEN 0 AND 6),
    rate_paise INTEGER NOT NULL CHECK (rate_paise >= 0),
    rate_unit TEXT NOT NULL,
    amount_paise INTEGER NOT NULL CHECK (amount_paise >= 0),
    line_metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (document_id) REFERENCES document(document_id) ON DELETE RESTRICT,
    FOREIGN KEY (commodity_id) REFERENCES commodity(commodity_id),
    FOREIGN KEY (purchaser_party_id) REFERENCES party(party_id),
    FOREIGN KEY (source_party_id) REFERENCES party(party_id),
    UNIQUE (document_id, line_number)
);

CREATE TABLE IF NOT EXISTS document_charge (
    document_charge_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    charge_rule_id TEXT,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    basis TEXT NOT NULL,
    rate_decimal TEXT NOT NULL,
    automatic_amount_paise INTEGER NOT NULL,
    final_amount_paise INTEGER NOT NULL,
    is_tax INTEGER NOT NULL DEFAULT 0 CHECK (is_tax IN (0, 1)),
    is_override INTEGER NOT NULL DEFAULT 0 CHECK (is_override IN (0, 1)),
    override_reason TEXT,
    ledger_account_id TEXT,
    tds_challan_id TEXT,
    challan_no TEXT,
    FOREIGN KEY (document_id) REFERENCES document(document_id) ON DELETE RESTRICT,
    FOREIGN KEY (charge_rule_id) REFERENCES charge_rule(charge_rule_id),
    FOREIGN KEY (ledger_account_id) REFERENCES account(account_id),
    UNIQUE (document_id, line_number),
    CHECK (is_override = 0 OR length(trim(COALESCE(override_reason, ''))) > 0)
);

CREATE TABLE IF NOT EXISTS inventory_movement (
    inventory_movement_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    document_id TEXT,
    document_line_id TEXT,
    commodity_id TEXT NOT NULL,
    warehouse_code TEXT NOT NULL DEFAULT 'MAIN',
    movement_type TEXT NOT NULL,
    quantity_scaled INTEGER NOT NULL,
    quantity_scale INTEGER NOT NULL CHECK (quantity_scale BETWEEN 0 AND 6),
    bags_scaled INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL UNIQUE,
    occurred_on TEXT NOT NULL,
    reversal_of_movement_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id),
    FOREIGN KEY (document_id) REFERENCES document(document_id),
    FOREIGN KEY (document_line_id) REFERENCES document_line(document_line_id),
    FOREIGN KEY (commodity_id) REFERENCES commodity(commodity_id),
    FOREIGN KEY (reversal_of_movement_id)
        REFERENCES inventory_movement(inventory_movement_id)
);

CREATE INDEX IF NOT EXISTS ix_inventory_balance
ON inventory_movement(financial_year_id, commodity_id, warehouse_code, occurred_on);
"""


def utc_now() -> str:
    """Return a stable UTC ISO timestamp."""
    return datetime.now(UTC).isoformat(timespec="seconds")


MASTER_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS city_master (
    city_id TEXT PRIMARY KEY,
    city_code TEXT,
    name TEXT NOT NULL COLLATE NOCASE,
    state_name TEXT,
    state_code TEXT,
    district_name TEXT,
    pincode TEXT,
    country TEXT,
    jurisdiction TEXT,
    focal_point TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transport_master (
    transport_id TEXT PRIMARY KEY,
    transport_code TEXT,
    name TEXT NOT NULL COLLATE NOCASE,
    gstin TEXT,
    vehicle_details TEXT,
    address TEXT,
    phone TEXT,
    contact_person TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS standard_narration (
    narration_id TEXT PRIMARY KEY,
    narration_text TEXT NOT NULL,
    short_code TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bank_master (
    bank_id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE,
    account_number TEXT,
    ifsc_code TEXT,
    branch_address TEXT,
    opening_balance_paise INTEGER NOT NULL DEFAULT 0,
    balance_side TEXT NOT NULL DEFAULT 'Dr',
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ifsc_master (
    ifsc_id TEXT PRIMARY KEY,
    bank_name TEXT,
    branch_name TEXT,
    ifsc_code TEXT NOT NULL,
    micr_code TEXT,
    city TEXT,
    state TEXT,
    address TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expense_master (
    expense_master_id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE,
    mandi_name TEXT,
    lines_json TEXT NOT NULL DEFAULT '[]',
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS i_form_expense_define (
    define_id TEXT PRIMARY KEY,
    commodity_id TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    dami TEXT,
    dami_on TEXT,
    dami_r_off TEXT,
    bonus TEXT,
    bonus_r_off TEXT,
    rdf_kkf_percent TEXT,
    rdf_r_off TEXT,
    mkt_percent TEXT,
    mkt_r_off TEXT,
    lines_json TEXT NOT NULL DEFAULT '[]',
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (commodity_id) REFERENCES commodity(commodity_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_i_form_expense_item_date
ON i_form_expense_define(commodity_id, effective_date)
WHERE is_deleted = 0;

CREATE TABLE IF NOT EXISTS cheque_print_setting (
    cheque_setting_id TEXT PRIMARY KEY,
    bank_name TEXT NOT NULL COLLATE NOCASE,
    settings_json TEXT NOT NULL DEFAULT '{}',
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_cheque_print_bank
ON cheque_print_setting(bank_name)
WHERE is_deleted = 0;

CREATE TABLE IF NOT EXISTS trading_account (
    trading_account_id TEXT PRIMARY KEY,
    trading_code TEXT,
    name TEXT NOT NULL COLLATE NOCASE,
    profit_loss_account TEXT,
    raw_commodity_ids_json TEXT NOT NULL DEFAULT '[]',
    finished_commodity_ids_json TEXT NOT NULL DEFAULT '[]',
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opening_stock (
    opening_stock_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    commodity_id TEXT NOT NULL,
    unit TEXT,
    bags INTEGER NOT NULL DEFAULT 0,
    quantity_scaled INTEGER NOT NULL DEFAULT 0,
    rate_paise INTEGER NOT NULL DEFAULT 0,
    amount_paise INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id),
    FOREIGN KEY (commodity_id) REFERENCES commodity(commodity_id)
);

CREATE TABLE IF NOT EXISTS stock_entry_master (
    stock_entry_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    entry_kind TEXT NOT NULL CHECK (entry_kind IN ('opening', 'closing')),
    entry_date TEXT NOT NULL,
    search_item TEXT,
    show_opening INTEGER NOT NULL DEFAULT 0 CHECK (show_opening IN (0, 1)),
    filter1 TEXT,
    filter2 TEXT,
    filter3 TEXT,
    filter4 TEXT,
    lines_json TEXT NOT NULL DEFAULT '[]',
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_entry_kind_date
ON stock_entry_master(financial_year_id, entry_kind, entry_date)
WHERE is_deleted = 0;

CREATE TABLE IF NOT EXISTS gst_doc_issue (
    gst_doc_issue_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    period_from TEXT NOT NULL,
    period_to TEXT NOT NULL,
    gst_nature TEXT NOT NULL,
    number_prefix TEXT NOT NULL DEFAULT '',
    serial_from TEXT NOT NULL,
    serial_to TEXT NOT NULL,
    total_count INTEGER NOT NULL CHECK (total_count >= 0),
    cancelled_count INTEGER NOT NULL DEFAULT 0 CHECK (cancelled_count >= 0),
    refreshed_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id),
    UNIQUE (financial_year_id, period_from, period_to, gst_nature, number_prefix)
);

CREATE INDEX IF NOT EXISTS ix_gst_doc_issue_period
ON gst_doc_issue(financial_year_id, period_from, period_to);

CREATE TABLE IF NOT EXISTS stock_adjustment (
    adjustment_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    adjustment_date TEXT NOT NULL,
    ref_no TEXT,
    commodity_id TEXT NOT NULL,
    adjustment_type TEXT NOT NULL,
    bags INTEGER NOT NULL DEFAULT 0,
    quantity_scaled INTEGER NOT NULL DEFAULT 0,
    rate_paise INTEGER NOT NULL DEFAULT 0,
    amount_paise INTEGER NOT NULL DEFAULT 0,
    remarks TEXT,
    godown TEXT,
    lines_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id),
    FOREIGN KEY (commodity_id) REFERENCES commodity(commodity_id)
);

CREATE TABLE IF NOT EXISTS company_settings (
    settings_key TEXT PRIMARY KEY,
    settings_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_attachment (
    attachment_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    mime_type TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES document(document_id)
);

CREATE TABLE IF NOT EXISTS bardana_movement (
    movement_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    movement_type TEXT NOT NULL CHECK (movement_type IN ('inward', 'outward', 'adjustment')),
    bardana_type TEXT NOT NULL CHECK (bardana_type IN ('jute', 'plastic', 'hdpe')),
    bags_signed INTEGER NOT NULL,
    party_id TEXT,
    document_id TEXT,
    remarks TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id),
    FOREIGN KEY (party_id) REFERENCES party(party_id),
    FOREIGN KEY (document_id) REFERENCES document(document_id)
);

CREATE INDEX IF NOT EXISTS ix_bardana_movement_year
ON bardana_movement(financial_year_id, bardana_type);

CREATE TABLE IF NOT EXISTS tds_challan (
    tds_challan_id TEXT PRIMARY KEY,
    financial_year_id TEXT NOT NULL,
    challan_display_id TEXT NOT NULL,
    challan_date TEXT NOT NULL,
    nature TEXT,
    filter_date_from TEXT NOT NULL,
    filter_date_to TEXT NOT NULL,
    deductee_code TEXT NOT NULL DEFAULT 'All',
    challan_no TEXT,
    minor_head TEXT NOT NULL DEFAULT '200',
    bsr_code TEXT,
    chq_no TEXT,
    tds_total_paise INTEGER NOT NULL DEFAULT 0,
    total_amt_paise INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (financial_year_id) REFERENCES financial_year(financial_year_id)
);

CREATE INDEX IF NOT EXISTS ix_tds_challan_year
ON tds_challan(financial_year_id, challan_date);
"""


def _ensure_master_tables(connection: sqlite3.Connection) -> None:
    """Create Phase 3 master tables and extend core masters."""
    connection.executescript(MASTER_TABLES_SQL)
    extensions = {
        "account": {"metadata_json": "TEXT NOT NULL DEFAULT '{}'"},
        "commodity": {"item_metadata_json": "TEXT NOT NULL DEFAULT '{}'"},
        "city_master": {
            "city_code": "TEXT",
            "country": "TEXT",
            "jurisdiction": "TEXT",
            "focal_point": "TEXT",
        },
        "transport_master": {
            "transport_code": "TEXT",
        },
        "bank_master": {
            "bank_code": "TEXT",
        },
        "ifsc_master": {
            "ifsc_number": "TEXT",
        },
        "opening_stock": {
            "account_id": "TEXT",
            "account_name": "TEXT",
            "entry_mm": "TEXT",
        },
    }
    for table, columns in extensions.items():
        existing = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate_catalog_schema(connection: sqlite3.Connection) -> None:
    """Apply additive catalog migrations (LAN users, company profile)."""
    installation_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(installation)").fetchall()
    }
    if "demo_started_at" not in installation_columns:
        connection.execute(
            "ALTER TABLE installation ADD COLUMN demo_started_at TEXT"
        )
        connection.execute(
            """
            UPDATE installation
            SET demo_started_at = date(created_at)
            WHERE demo_started_at IS NULL
            """
        )
    columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(company_catalog)").fetchall()
    }
    if "company_profile" not in columns:
        connection.execute(
            """
            ALTER TABLE company_catalog
            ADD COLUMN company_profile TEXT NOT NULL DEFAULT 'standard'
            """
        )
        connection.execute(
            """
            UPDATE company_catalog
            SET company_profile = 'kachi'
            WHERE name LIKE '%kachi%' COLLATE NOCASE
                OR name LIKE '%dasti%' COLLATE NOCASE
            """
        )
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_user (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'munim', 'operator', 'clerk', 'readonly')),
            can_view_kachi INTEGER NOT NULL DEFAULT 0 CHECK (can_view_kachi IN (0, 1)),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_session (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES app_user(user_id)
        );
        CREATE INDEX IF NOT EXISTS ix_app_session_user ON app_session(user_id, expires_at);
        CREATE TABLE IF NOT EXISTS app_user_permission (
            user_id TEXT NOT NULL,
            permission_key TEXT NOT NULL,
            access_level TEXT NOT NULL CHECK (access_level IN ('read', 'write')),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            valid_until TEXT,
            PRIMARY KEY (user_id, permission_key),
            FOREIGN KEY (user_id) REFERENCES app_user(user_id)
        );
        """
    )
    user_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(app_user)").fetchall()
    }
    if "use_custom_menu" not in user_columns:
        connection.execute(
            """
            ALTER TABLE app_user
            ADD COLUMN use_custom_menu INTEGER NOT NULL DEFAULT 0 CHECK (use_custom_menu IN (0, 1))
            """
        )
    if "access_valid_until" not in user_columns:
        connection.execute("ALTER TABLE app_user ADD COLUMN access_valid_until TEXT")


def _drop_legacy_sync_tables(connection: sqlite3.Connection) -> None:
    """Remove obsolete multi-device synchronization tables from company databases."""
    for table in (
        "sync_conflict",
        "sync_peer_cursor",
        "sync_package_receipt",
        "sync_changelog",
        "sync_sequence",
    ):
        connection.execute(f"DROP TABLE IF EXISTS {table}")


def migrate_company_schema(connection: sqlite3.Connection) -> None:
    """Apply additive schema migrations while preserving existing company data."""
    _ensure_master_tables(connection)
    migrations = {
        "party": {
            "related_name": "TEXT",
            "father_name": "TEXT",
            "agricultural_group": "TEXT",
            "village_name": "TEXT",
            "credit_limit_paise": "INTEGER NOT NULL DEFAULT 0",
        },
        "document": {
            "commodity_transfer_account_id": "TEXT",
            "gate_pass_required": "INTEGER NOT NULL DEFAULT 0",
            "self_purchase": "INTEGER NOT NULL DEFAULT 0",
            "dispatch_time": "TEXT",
            "gr_date": "TEXT",
            "freight_paise": "INTEGER NOT NULL DEFAULT 0",
            "freight_direction": "TEXT NOT NULL DEFAULT 'add'",
            "advance_cash_paise": "INTEGER NOT NULL DEFAULT 0",
            "balance_paise": "INTEGER NOT NULL DEFAULT 0",
            "insurance_number": "TEXT",
            "packing_material_transfer": "INTEGER NOT NULL DEFAULT 0",
            "stock_sale": "INTEGER NOT NULL DEFAULT 0",
            "multi_tax": "INTEGER NOT NULL DEFAULT 0",
            "cash_account_id": "TEXT",
            "advance_receipt_voucher_id": "TEXT",
            "header_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        },
        "document_line": {
            "purchaser_party_id": "TEXT",
            "gate_pass_number": "TEXT",
            "source_party_id": "TEXT",
            "source_reference_number": "TEXT",
            "line_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
            "igst_paise": "INTEGER NOT NULL DEFAULT 0 CHECK (igst_paise >= 0)",
            "cgst_paise": "INTEGER NOT NULL DEFAULT 0 CHECK (cgst_paise >= 0)",
            "sgst_paise": "INTEGER NOT NULL DEFAULT 0 CHECK (sgst_paise >= 0)",
            "cess_paise": "INTEGER NOT NULL DEFAULT 0 CHECK (cess_paise >= 0)",
            "uqc": "TEXT",
        },
        "commodity": {
            "uqc": "TEXT",
        },
        "charge_rule": {
            "charge_bearer": (
                "TEXT NOT NULL DEFAULT 'buyer' "
                "CHECK (charge_bearer IN ('farmer', 'buyer', 'firm'))"
            ),
        },
        "voucher": {
            "entry_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        },
        "voucher_line": {
            "line_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        },
        "document_charge": {
            "tds_challan_id": "TEXT",
            "challan_no": "TEXT",
        },
        "stock_adjustment": {
            "godown": "TEXT",
            "lines_json": "TEXT NOT NULL DEFAULT '{}'",
        },
    }
    for table, columns in migrations.items():
        existing = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )
    _seed_sale_bill_defaults(connection)
    _seed_tier_expense_rules(connection)
    _drop_legacy_sync_tables(connection)
    connection.execute(
        """
        UPDATE party
        SET father_name = related_name
        WHERE (father_name IS NULL OR father_name = '')
            AND related_name IS NOT NULL AND related_name != ''
        """
    )
    party_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(party)").fetchall()
    }
    if "agricultural_group" in party_columns:
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_party_agricultural_group
            ON party(agricultural_group, is_deleted)
            """
        )
    connection.execute(
        """
        UPDATE commodity
        SET uqc = COALESCE(
            NULLIF(TRIM(uqc), ''),
            NULLIF(TRIM(json_extract(item_metadata_json, '$.uqc')), '')
        )
        WHERE uqc IS NULL OR TRIM(uqc) = ''
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_version(version, applied_at)
        VALUES (?, ?)
        """,
        (SCHEMA_VERSION, utc_now()),
    )


def _seed_sale_bill_defaults(connection: sqlite3.Connection) -> None:
    """Install editable Haryana sale-bill defaults without replacing user rules."""
    timestamp = utc_now()
    account_specs = {
        "DAMI": ("Dami / Commission", "income"),
        "LABOUR": ("Labour Recovery", "income"),
        "AUCTION": ("Auction Charges", "income"),
        "MARKET_FEE": ("Market Fee Payable", "liability"),
        "HRDF": ("HRDF Payable", "liability"),
        "ASSOCIATION": ("Association Charges Payable", "liability"),
        "SGST": ("SGST Payable", "liability"),
        "CGST": ("CGST Payable", "liability"),
        "IGST": ("IGST Payable", "liability"),
        "TDS": ("TDS Payable", "liability"),
    }
    account_ids: dict[str, str] = {}
    for code, (name, account_type) in account_specs.items():
        row = connection.execute(
            """
            SELECT account_id FROM account
            WHERE financial_year_id IS NULL AND name = ? COLLATE NOCASE
                AND is_deleted = 0
            """,
            (name,),
        ).fetchone()
        if row is None:
            account_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO account(
                    account_id, name, account_type, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (account_id, name, account_type, timestamp, timestamp),
            )
        else:
            account_id = str(row["account_id"])
        account_ids[code] = account_id

    rules = (
        ("DAMI", "Dami", "amount", "percentage", "2.50", 0),
        ("LABOUR", "Labour", "bag", "fixed", "2.70", 0),
        ("AUCTION", "Auction", "amount", "percentage", "0.10", 0),
        ("MARKET_FEE", "Market Fees", "amount", "percentage", "2.00", 0),
        ("HRDF", "HRDF", "amount", "percentage", "2.00", 0),
        ("ASSOCIATION", "Association", "amount", "percentage", "0.02", 0),
        ("SGST", "SGST", "amount", "percentage", "2.50", 1),
        ("CGST", "CGST", "amount", "percentage", "2.50", 1),
        ("IGST", "IGST", "amount", "percentage", "5.00", 1),
    )
    transaction_rules = (
        ("sale_invoice", rules),
        ("gst_debit_note", rules),
        ("gst_credit_note", rules),
        ("gst_expense_voucher", rules),
        ("purchase_invoice", rules),
        ("form_i_debit", rules),
        ("consignment_debit", rules),
        ("consignment_credit", rules),
        (
            "form_i_credit",
            tuple(
                rule
                for rule in rules
                if rule[0] in {"DAMI", "LABOUR", "AUCTION", "ASSOCIATION"}
            ),
        ),
    )
    for transaction_type, selected_rules in transaction_rules:
        for code, label, basis, mode, rate, is_tax in selected_rules:
            exists = connection.execute(
                """
                SELECT 1 FROM charge_rule
                WHERE transaction_type = ? AND code = ? AND is_deleted = 0
                LIMIT 1
                """,
                (transaction_type, code),
            ).fetchone()
            if exists is not None:
                continue
            connection.execute(
                """
                INSERT INTO charge_rule(
                    charge_rule_id, code, label, transaction_type,
                    basis, mode, rate_decimal, direction, is_tax,
                    ledger_account_id, priority, effective_from,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'add', ?, ?, 100, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    code,
                    label,
                    transaction_type,
                    basis,
                    mode,
                    rate,
                    is_tax,
                    account_ids[code],
                    "2000-04-01",
                    timestamp,
                    timestamp,
                ),
            )


def _seed_tier_expense_rules(connection: sqlite3.Connection) -> None:
    """Install Phase 3 multi-tier labour/expense rules when absent."""
    from .mandi_business import default_tier_expense_templates

    timestamp = utc_now()
    charge_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(charge_rule)").fetchall()
    }
    has_bearer = "charge_bearer" in charge_columns
    labour_account = connection.execute(
        """
        SELECT account_id FROM account
        WHERE financial_year_id IS NULL AND name LIKE '%Labour%' COLLATE NOCASE
            AND is_deleted = 0 LIMIT 1
        """
    ).fetchone()
    income_account = connection.execute(
        """
        SELECT account_id FROM account
        WHERE financial_year_id IS NULL AND name LIKE '%Commission%' COLLATE NOCASE
            AND is_deleted = 0 LIMIT 1
        """
    ).fetchone()
    default_ledger = str(labour_account["account_id"]) if labour_account else None
    commission_ledger = str(income_account["account_id"]) if income_account else default_ledger
    for template in default_tier_expense_templates():
        bearer = str(template["charge_bearer"])
        ledger = commission_ledger if bearer == "buyer" else default_ledger
        for transaction_type in template["transaction_types"]:
            exists = connection.execute(
                """
                SELECT 1 FROM charge_rule
                WHERE transaction_type = ? AND code = ? AND is_deleted = 0
                LIMIT 1
                """,
                (transaction_type, template["code"]),
            ).fetchone()
            if exists is not None:
                continue
            if has_bearer:
                connection.execute(
                    """
                    INSERT INTO charge_rule(
                        charge_rule_id, code, label, transaction_type,
                        basis, mode, rate_decimal, direction, is_tax,
                        ledger_account_id, priority, effective_from,
                        charge_bearer, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'deduct', 0, ?, 110, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        template["code"],
                        template["label"],
                        transaction_type,
                        template["basis"],
                        template["mode"],
                        template["rate_decimal"],
                        ledger,
                        "2000-04-01",
                        bearer,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO charge_rule(
                        charge_rule_id, code, label, transaction_type,
                        basis, mode, rate_decimal, direction, is_tax,
                        ledger_account_id, priority, effective_from,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'deduct', 0, ?, 110, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        template["code"],
                        template["label"],
                        transaction_type,
                        template["basis"],
                        template["mode"],
                        template["rate_decimal"],
                        ledger,
                        "2000-04-01",
                        timestamp,
                        timestamp,
                    ),
                )


class DatabaseManager:
    """Create and access the installation catalog and company databases."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize paths without opening persistent connections."""
        self.data_dir = resolve_data_dir(data_dir)
        self.catalog_path = self.data_dir / "catalog.db"
        self.companies_dir = self.data_dir / "companies"

    def initialize(self) -> None:
        """Create application directories and catalog schema idempotently."""
        self.companies_dir.mkdir(parents=True, exist_ok=True)
        with self.connect(self.catalog_path) as connection:
            connection.executescript(CATALOG_SCHEMA)
            migrate_catalog_schema(connection)
            existing = connection.execute("SELECT installation_id FROM installation").fetchone()
            if existing is None:
                started = date.today().isoformat()
                connection.execute(
                    """
                    INSERT INTO installation(installation_id, created_at, demo_started_at)
                    VALUES (?, ?, ?)
                    """,
                    (str(uuid.uuid4()), utc_now(), started),
                )
            device = connection.execute("SELECT device_id FROM device_identity").fetchone()
            if device is None:
                connection.execute(
                    """
                    INSERT INTO device_identity(device_id, device_name, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (str(uuid.uuid4()), "This Windows PC", utc_now()),
                )
            company_files = connection.execute(
                """
                SELECT database_filename FROM company_catalog
                WHERE is_deleted = 0
                """
            ).fetchall()
        for row in company_files:
            company_path = self.companies_dir / str(row["database_filename"])
            if company_path.exists():
                with self.connect(company_path) as company_connection:
                    company_connection.executescript(COMPANY_SCHEMA)
                    migrate_company_schema(company_connection)
                    company_connection.execute(
                        """
                        INSERT OR IGNORE INTO schema_version(version, applied_at)
                        VALUES (1, ?)
                        """,
                        (utc_now(),),
                    )
        logger.info("Database catalog initialized", extra={"path": str(self.catalog_path)})

    @contextmanager
    def connect(self, path: Path) -> Iterator[sqlite3.Connection]:
        """Open a hardened SQLite transaction connection.

        Args:
            path: Database file path.

        Yields:
            Configured SQLite connection committed on successful exit.

        Raises:
            DatabaseError: If SQLite rejects the operation.
        """
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(path, timeout=10)
            connection.row_factory = sqlite3.Row
            configure_sqlite_connection(connection)
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            if connection is not None:
                connection.rollback()
            raise DatabaseError(f"SQLite operation failed: {exc}") from exc
        finally:
            if connection is not None:
                connection.close()

    def installation_id(self) -> str:
        """Return the permanent random installation identifier."""
        with self.connect(self.catalog_path) as connection:
            row = connection.execute("SELECT installation_id FROM installation").fetchone()
        if row is None:
            raise DatabaseError("Installation identity is missing")
        return str(row["installation_id"])

    def device_id(self) -> str:
        """Return the permanent random device identifier."""
        with self.connect(self.catalog_path) as connection:
            row = connection.execute("SELECT device_id FROM device_identity").fetchone()
        if row is None:
            raise DatabaseError("Device identity is missing")
        return str(row["device_id"])

    def list_companies(self) -> list[dict[str, str]]:
        """Return active companies ordered for startup selection."""
        with self.connect(self.catalog_path) as connection:
            rows = connection.execute(
                """
                SELECT company_id, name, database_filename, company_profile
                FROM company_catalog
                WHERE is_deleted = 0
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def set_company_profile(self, company_id: str, profile: str) -> dict[str, str]:
        """Mark a company as standard (Pakki) or kachi for menu visibility."""
        clean = str(profile or "").strip().lower()
        if clean not in {"standard", "kachi"}:
            raise ValidationError("Company profile must be standard or kachi")
        timestamp = utc_now()
        with self.connect(self.catalog_path) as connection:
            updated = connection.execute(
                """
                UPDATE company_catalog
                SET company_profile = ?, updated_at = ?
                WHERE company_id = ? AND is_deleted = 0
                """,
                (clean, timestamp, str(company_id)),
            ).rowcount
        if updated != 1:
            raise ValidationError("Company not found")
        return {"company_id": str(company_id), "company_profile": clean}

    def create_company(
        self,
        name: str,
        start_year: int,
        *,
        company_profile: str = "standard",
    ) -> dict[str, str]:
        """Create an isolated company database and initial financial year.

        Args:
            name: Display/legal company name.
            start_year: Starting calendar year for the initial financial year.

        Returns:
            New company summary.

        Raises:
            ValidationError: If the company name is empty.
            DatabaseError: If company creation is not completed.
        """
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValidationError("Company name is required")
        profile = company_profile.strip().lower()
        if profile not in {"standard", "kachi"}:
            raise ValidationError("Company profile must be standard or kachi")
        year = FinancialYear(start_year)
        company_id = str(uuid.uuid4())
        database_filename = f"{company_id}.db"
        company_path = self.companies_dir / database_filename
        timestamp = utc_now()
        try:
            with self.connect(company_path) as connection:
                connection.executescript(COMPANY_SCHEMA)
                migrate_company_schema(connection)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO schema_version(version, applied_at)
                    VALUES (1, ?)
                    """,
                    (timestamp,),
                )
                connection.execute(
                    """
                    INSERT INTO company(
                        company_id, name, legal_name, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (company_id, clean_name, clean_name, timestamp, timestamp),
                )
                connection.execute(
                    """
                    INSERT INTO financial_year(
                        financial_year_id, start_year, starts_on, ends_on,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        start_year,
                        year.starts_on.isoformat(),
                        year.ends_on.isoformat(),
                        timestamp,
                        timestamp,
                    ),
                )
            with self.connect(self.catalog_path) as connection:
                connection.execute(
                    """
                    INSERT INTO company_catalog(
                        company_id, name, database_filename, company_profile,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_id,
                        clean_name,
                        database_filename,
                        profile,
                        timestamp,
                        timestamp,
                    ),
                )
        except Exception:
            if company_path.exists():
                company_path.unlink()
            raise
        return {
            "company_id": company_id,
            "name": clean_name,
            "database_filename": database_filename,
            "company_profile": profile,
        }

    def company_path(self, company_id: str) -> Path:
        """Resolve a catalog company ID to its validated database path."""
        with self.connect(self.catalog_path) as connection:
            row = connection.execute(
                """
                SELECT database_filename FROM company_catalog
                WHERE company_id = ? AND is_deleted = 0
                """,
                (company_id,),
            ).fetchone()
        if row is None:
            raise ValidationError("Company does not exist")
        path = (self.companies_dir / str(row["database_filename"])).resolve()
        if path.parent != self.companies_dir.resolve():
            raise DatabaseError("Invalid company database path")
        return path

    def list_financial_years(self, company_id: str) -> list[dict[str, object]]:
        """Return all financial years for a company, newest first."""
        path = self.company_path(company_id)
        with self.connect(path) as connection:
            rows = connection.execute(
                """
                SELECT financial_year_id, start_year, starts_on, ends_on, is_locked
                FROM financial_year ORDER BY start_year DESC
                """
            ).fetchall()
        return [
            {
                **dict(row),
                "label": FinancialYear(int(row["start_year"])).label,
                "is_locked": bool(row["is_locked"]),
            }
            for row in rows
        ]
