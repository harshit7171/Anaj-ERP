"""Reference ERP master data (city, transport, bank, items, expenses)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .database import utc_now
from .errors import ValidationError
from .gst_compliance import validate_hsn
from .gst_compliance import validate_uqc

_ACCOUNT_METADATA_KEYS = (
    "short_name",
    "print_name",
    "account_code",
    "group_name",
    "gst_type",
    "party_gst_type",
    "ac_category",
    "show_tcs_msg",
    "farmer_arthia",
    "tds_deductee_code",
    "local_central",
    "main_head",
    "uniq_id",
    "distance_kms",
    "contact_person",
    "address_line2",
    "address_line3",
    "phone",
    "phone2",
    "fax",
    "web",
    "dob",
    "aadhar_part1",
    "aadhar_part2",
    "aadhar_part3",
    "trading_ac",
    "depreciation_rate",
    "sec_code",
    "gp_rate",
    "profit_share",
    "bank_ac_no",
    "consolidate_yn",
    "bank_ifsc",
    "lock_date",
    "main_ac",
    "remarks",
    "tan",
    "interest_rate",
    "tds_rate",
    "is_farmer",
    "is_arthia",
    "pincode",
    "email",
    "mobile1",
    "mobile2",
)


def _parse_account_metadata(raw: object | None) -> dict[str, object]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _opening_side_label(debit_paise: int, credit_paise: int) -> tuple[str, str]:
    debit = int(debit_paise or 0)
    credit = int(credit_paise or 0)
    if debit >= credit:
        return "Debit", str(abs(debit - credit) / 100)
    return "Credit", str(abs(credit - debit) / 100)


class MasterService:
    """CRUD for extended masters on the active company database."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.accounting = AccountingService(databases, company_id)

    def list_cities(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT city_id, city_code, name, state_name, state_code, district_name,
                    pincode, country, jurisdiction, focal_point
                FROM city_master WHERE is_deleted = 0
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def save_city(self, payload: dict[str, Any]) -> dict[str, object]:
        city_id = str(payload.get("city_id") or uuid.uuid4())
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValidationError("City name is required")
        timestamp = utc_now()
        focal = str(payload.get("focal_point", "N")).strip().upper() or "N"
        if focal not in {"Y", "N"}:
            focal = "N"
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO city_master(
                    city_id, city_code, name, state_name, state_code, district_name, pincode,
                    country, jurisdiction, focal_point, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(city_id) DO UPDATE SET
                    city_code = excluded.city_code,
                    name = excluded.name,
                    state_name = excluded.state_name,
                    state_code = excluded.state_code,
                    district_name = excluded.district_name,
                    pincode = excluded.pincode,
                    country = excluded.country,
                    jurisdiction = excluded.jurisdiction,
                    focal_point = excluded.focal_point,
                    updated_at = excluded.updated_at
                """,
                (
                    city_id,
                    str(payload.get("city_code", "")).strip() or None,
                    name,
                    str(payload.get("state_name", "")).strip() or None,
                    str(payload.get("state_code", "")).strip() or None,
                    str(payload.get("district_name", "")).strip() or None,
                    str(payload.get("pincode", "")).strip() or None,
                    str(payload.get("country", "")).strip() or None,
                    str(payload.get("jurisdiction", "")).strip() or None,
                    focal,
                    timestamp,
                    timestamp,
                ),
            )
        return {"city_id": city_id, "name": name}

    def get_city(self, city_key: str) -> dict[str, object]:
        clean = str(city_key or "").strip()
        if not clean:
            raise ValidationError("City is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT city_id, city_code, name, state_name, state_code, district_name,
                    pincode, country, jurisdiction, focal_point
                FROM city_master
                WHERE is_deleted = 0
                  AND (city_id = ? OR city_code = ?)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
        if row is None:
            raise ValidationError("City not found")
        return dict(row)

    def delete_city(self, city_key: str) -> dict[str, object]:
        clean = str(city_key or "").strip()
        if not clean:
            raise ValidationError("City is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT city_id FROM city_master
                WHERE is_deleted = 0 AND (city_id = ? OR city_code = ?)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
            if row is None:
                raise ValidationError("City not found")
            city_id = str(row["city_id"])
            connection.execute(
                """
                UPDATE city_master
                SET is_deleted = 1, updated_at = ?
                WHERE city_id = ? AND is_deleted = 0
                """,
                (timestamp, city_id),
            )
        return {"city_id": city_id, "deleted": True}

    def list_transports(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT transport_id, transport_code, name, gstin, vehicle_details, address,
                    phone, contact_person
                FROM transport_master WHERE is_deleted = 0
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def save_transport(self, payload: dict[str, Any]) -> dict[str, object]:
        transport_id = str(payload.get("transport_id") or uuid.uuid4())
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValidationError("Transport name is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO transport_master(
                    transport_id, transport_code, name, gstin, vehicle_details, address, phone,
                    contact_person, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(transport_id) DO UPDATE SET
                    transport_code = excluded.transport_code,
                    name = excluded.name,
                    gstin = excluded.gstin,
                    vehicle_details = excluded.vehicle_details,
                    address = excluded.address,
                    phone = excluded.phone,
                    contact_person = excluded.contact_person,
                    updated_at = excluded.updated_at
                """,
                (
                    transport_id,
                    str(payload.get("transport_code", "")).strip() or None,
                    name,
                    str(payload.get("gstin", "")).strip() or None,
                    str(payload.get("vehicle_details", "")).strip() or None,
                    str(payload.get("address", "")).strip() or None,
                    str(payload.get("phone", "")).strip() or None,
                    str(payload.get("contact_person", "")).strip() or None,
                    timestamp,
                    timestamp,
                ),
            )
        return {"transport_id": transport_id, "name": name}

    def get_transport(self, transport_key: str) -> dict[str, object]:
        clean = str(transport_key or "").strip()
        if not clean:
            raise ValidationError("Transport is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT transport_id, transport_code, name, gstin, vehicle_details, address,
                    phone, contact_person
                FROM transport_master
                WHERE is_deleted = 0
                  AND (transport_id = ? OR transport_code = ?)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
        if row is None:
            raise ValidationError("Transport not found")
        return dict(row)

    def delete_transport(self, transport_key: str) -> dict[str, object]:
        clean = str(transport_key or "").strip()
        if not clean:
            raise ValidationError("Transport is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT transport_id FROM transport_master
                WHERE is_deleted = 0 AND (transport_id = ? OR transport_code = ?)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
            if row is None:
                raise ValidationError("Transport not found")
            transport_id = str(row["transport_id"])
            connection.execute(
                """
                UPDATE transport_master
                SET is_deleted = 1, updated_at = ?
                WHERE transport_id = ? AND is_deleted = 0
                """,
                (timestamp, transport_id),
            )
        return {"transport_id": transport_id, "deleted": True}

    def list_narrations(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT narration_id, narration_text, short_code
                FROM standard_narration WHERE is_deleted = 0
                ORDER BY narration_text COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def save_narration(self, payload: dict[str, Any]) -> dict[str, object]:
        narration_id = str(payload.get("narration_id") or uuid.uuid4())
        text = str(payload.get("narration_text", "")).strip()
        if not text:
            raise ValidationError("Narration text is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO standard_narration(
                    narration_id, narration_text, short_code, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(narration_id) DO UPDATE SET
                    narration_text = excluded.narration_text,
                    short_code = excluded.short_code,
                    updated_at = excluded.updated_at
                """,
                (
                    narration_id,
                    text,
                    str(payload.get("short_code", "")).strip() or None,
                    timestamp,
                    timestamp,
                ),
            )
        return {"narration_id": narration_id, "narration_text": text}

    def get_narration(self, narration_id: str) -> dict[str, object]:
        clean = str(narration_id or "").strip()
        if not clean:
            raise ValidationError("Narration is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT narration_id, narration_text, short_code
                FROM standard_narration
                WHERE is_deleted = 0
                  AND (narration_id = ? OR short_code = ?)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
        if row is None:
            raise ValidationError("Narration not found")
        return dict(row)

    def delete_narration(self, narration_id: str) -> dict[str, object]:
        clean = str(narration_id or "").strip()
        if not clean:
            raise ValidationError("Narration is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            updated = connection.execute(
                """
                UPDATE standard_narration
                SET is_deleted = 1, updated_at = ?
                WHERE narration_id = ? AND is_deleted = 0
                """,
                (timestamp, clean),
            )
            if updated.rowcount == 0:
                raise ValidationError("Narration not found")
        return {"narration_id": clean, "deleted": True}

    def list_banks(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT bank_id, bank_code, name, account_number, ifsc_code, branch_address,
                    opening_balance_paise, balance_side
                FROM bank_master WHERE is_deleted = 0
                ORDER BY bank_code COLLATE NOCASE, name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_bank(self, bank_key: str) -> dict[str, object]:
        clean = str(bank_key or "").strip()
        if not clean:
            raise ValidationError("Bank is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT bank_id, bank_code, name, account_number, ifsc_code, branch_address,
                    opening_balance_paise, balance_side
                FROM bank_master
                WHERE is_deleted = 0
                  AND (bank_id = ? OR bank_code = ? OR name = ? COLLATE NOCASE)
                LIMIT 1
                """,
                (clean, clean, clean),
            ).fetchone()
        if row is None:
            raise ValidationError("Bank not found")
        return dict(row)

    def save_bank(self, payload: dict[str, Any]) -> dict[str, object]:
        bank_id = str(payload.get("bank_id") or uuid.uuid4())
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValidationError("Bank name is required")
        bank_code = str(payload.get("bank_code", "")).strip() or None
        timestamp = utc_now()
        opening = int(payload.get("opening_balance_paise", 0))
        side = str(payload.get("balance_side", "Dr")).strip() or "Dr"
        with self.databases.connect(self.database_path) as connection:
            if bank_code:
                duplicate = connection.execute(
                    """
                    SELECT bank_id FROM bank_master
                    WHERE is_deleted = 0
                      AND bank_code = ?
                      AND bank_id != ?
                    LIMIT 1
                    """,
                    (bank_code, bank_id),
                ).fetchone()
                if duplicate is not None:
                    raise ValidationError("Bank ID already exists")
            connection.execute(
                """
                INSERT INTO bank_master(
                    bank_id, bank_code, name, account_number, ifsc_code, branch_address,
                    opening_balance_paise, balance_side, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bank_id) DO UPDATE SET
                    bank_code = excluded.bank_code,
                    name = excluded.name,
                    account_number = excluded.account_number,
                    ifsc_code = excluded.ifsc_code,
                    branch_address = excluded.branch_address,
                    opening_balance_paise = excluded.opening_balance_paise,
                    balance_side = excluded.balance_side,
                    updated_at = excluded.updated_at
                """,
                (
                    bank_id,
                    bank_code,
                    name,
                    str(payload.get("account_number", "")).strip() or None,
                    str(payload.get("ifsc_code", "")).strip() or None,
                    str(payload.get("branch_address", "")).strip() or None,
                    opening,
                    side,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_bank(bank_id)

    def delete_bank(self, bank_key: str) -> dict[str, object]:
        clean = str(bank_key or "").strip()
        if not clean:
            raise ValidationError("Bank is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT bank_id FROM bank_master
                WHERE is_deleted = 0
                  AND (bank_id = ? OR bank_code = ? OR name = ? COLLATE NOCASE)
                LIMIT 1
                """,
                (clean, clean, clean),
            ).fetchone()
            if row is None:
                raise ValidationError("Bank not found")
            bank_id = str(row["bank_id"])
            connection.execute(
                """
                UPDATE bank_master
                SET is_deleted = 1, updated_at = ?
                WHERE bank_id = ? AND is_deleted = 0
                """,
                (timestamp, bank_id),
            )
        return {"bank_id": bank_id, "deleted": True}

    def list_ifsc(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT ifsc_id, ifsc_number, bank_name, branch_name, ifsc_code, micr_code, city,
                    state, address
                FROM ifsc_master WHERE is_deleted = 0
                ORDER BY ifsc_number COLLATE NOCASE, ifsc_code COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_ifsc(self, ifsc_key: str) -> dict[str, object]:
        clean = str(ifsc_key or "").strip()
        if not clean:
            raise ValidationError("IFSC record is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT ifsc_id, ifsc_number, bank_name, branch_name, ifsc_code, micr_code, city,
                    state, address
                FROM ifsc_master
                WHERE is_deleted = 0
                  AND (
                    ifsc_id = ?
                    OR ifsc_number = ?
                    OR ifsc_code = ? COLLATE NOCASE
                  )
                LIMIT 1
                """,
                (clean, clean, clean.upper()),
            ).fetchone()
        if row is None:
            raise ValidationError("IFSC record not found")
        return dict(row)

    def save_ifsc(self, payload: dict[str, Any]) -> dict[str, object]:
        ifsc_id = str(payload.get("ifsc_id") or uuid.uuid4())
        code = str(payload.get("ifsc_code", "")).strip().upper()
        if not code:
            raise ValidationError("IFSC code is required")
        if len(code) != 11:
            raise ValidationError("IFSC code must be 11 characters")
        ifsc_number = str(payload.get("ifsc_number", "")).strip() or None
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            duplicate_code = connection.execute(
                """
                SELECT ifsc_id FROM ifsc_master
                WHERE is_deleted = 0 AND ifsc_code = ? COLLATE NOCASE AND ifsc_id != ?
                LIMIT 1
                """,
                (code, ifsc_id),
            ).fetchone()
            if duplicate_code is not None:
                raise ValidationError("IFSC code already exists")
            if ifsc_number:
                duplicate_no = connection.execute(
                    """
                    SELECT ifsc_id FROM ifsc_master
                    WHERE is_deleted = 0 AND ifsc_number = ? AND ifsc_id != ?
                    LIMIT 1
                    """,
                    (ifsc_number, ifsc_id),
                ).fetchone()
                if duplicate_no is not None:
                    raise ValidationError("IFSC ID already exists")
            connection.execute(
                """
                INSERT INTO ifsc_master(
                    ifsc_id, ifsc_number, bank_name, branch_name, ifsc_code, micr_code, city, state,
                    address, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ifsc_id) DO UPDATE SET
                    ifsc_number = excluded.ifsc_number,
                    bank_name = excluded.bank_name,
                    branch_name = excluded.branch_name,
                    ifsc_code = excluded.ifsc_code,
                    micr_code = excluded.micr_code,
                    city = excluded.city,
                    state = excluded.state,
                    address = excluded.address,
                    updated_at = excluded.updated_at
                """,
                (
                    ifsc_id,
                    ifsc_number,
                    str(payload.get("bank_name", "")).strip() or None,
                    str(payload.get("branch_name", "")).strip() or None,
                    code,
                    str(payload.get("micr_code", "")).strip() or None,
                    str(payload.get("city", "")).strip() or None,
                    str(payload.get("state", "")).strip() or None,
                    str(payload.get("address", "")).strip() or None,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_ifsc(ifsc_id)

    def delete_ifsc(self, ifsc_key: str) -> dict[str, object]:
        clean = str(ifsc_key or "").strip()
        if not clean:
            raise ValidationError("IFSC record is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT ifsc_id FROM ifsc_master
                WHERE is_deleted = 0
                  AND (
                    ifsc_id = ?
                    OR ifsc_number = ?
                    OR ifsc_code = ? COLLATE NOCASE
                  )
                LIMIT 1
                """,
                (clean, clean, clean.upper()),
            ).fetchone()
            if row is None:
                raise ValidationError("IFSC record not found")
            record_id = str(row["ifsc_id"])
            connection.execute(
                """
                UPDATE ifsc_master
                SET is_deleted = 1, updated_at = ?
                WHERE ifsc_id = ? AND is_deleted = 0
                """,
                (timestamp, record_id),
            )
        return {"ifsc_id": record_id, "deleted": True}

    def save_expense_master(self, payload: dict[str, Any]) -> dict[str, object]:
        master_id = str(payload.get("expense_master_id") or uuid.uuid4())
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValidationError("Expense master name is required")
        lines = payload.get("lines", [])
        if isinstance(lines, list):
            for index, raw in enumerate(lines, start=1):
                if not isinstance(raw, dict):
                    continue
                if not str(raw.get("expense_name", "")).strip():
                    continue
                for flag in ("rcm_applicable", "blocked_itc"):
                    value = str(raw.get(flag, "No")).strip()
                    if value.lower() not in {"yes", "no", "y", "n"}:
                        raise ValidationError(
                            f"Line {index}: {flag} must be Yes or No"
                        )
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO expense_master(
                    expense_master_id, name, mandi_name, lines_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(expense_master_id) DO UPDATE SET
                    name = excluded.name,
                    mandi_name = excluded.mandi_name,
                    lines_json = excluded.lines_json,
                    updated_at = excluded.updated_at
                """,
                (
                    master_id,
                    name,
                    str(payload.get("mandi_name", "")).strip() or None,
                    json.dumps(lines, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        return {"expense_master_id": master_id, "name": name}

    def list_expense_masters(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT expense_master_id, name, mandi_name, lines_json
                FROM expense_master WHERE is_deleted = 0
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            item["lines"] = json.loads(str(item.pop("lines_json") or "[]"))
            result.append(item)
        return result

    def get_expense_master(self, expense_key: str) -> dict[str, object]:
        clean = str(expense_key or "").strip()
        if not clean:
            raise ValidationError("Expense master is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT expense_master_id, name, mandi_name, lines_json
                FROM expense_master
                WHERE is_deleted = 0
                  AND (expense_master_id = ? OR name = ? COLLATE NOCASE)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
        if row is None:
            raise ValidationError("Expense master not found")
        item = dict(row)
        item["lines"] = json.loads(str(item.pop("lines_json") or "[]"))
        return item

    def delete_expense_master(self, expense_key: str) -> dict[str, object]:
        clean = str(expense_key or "").strip()
        if not clean:
            raise ValidationError("Expense master is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT expense_master_id FROM expense_master
                WHERE is_deleted = 0
                  AND (expense_master_id = ? OR name = ? COLLATE NOCASE)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
            if row is None:
                raise ValidationError("Expense master not found")
            master_id = str(row["expense_master_id"])
            connection.execute(
                """
                UPDATE expense_master
                SET is_deleted = 1, updated_at = ?
                WHERE expense_master_id = ? AND is_deleted = 0
                """,
                (timestamp, master_id),
            )
        return {"expense_master_id": master_id, "deleted": True}

    _CHEQUE_PRINT_SETTING_KEYS: tuple[str, ...] = (
        "width_of_chq",
        "height_of_chq",
        "printer_mode",
        "date_from_top",
        "date_from_left",
        "name_from_top",
        "name_from_left",
        "name_char_count",
        "amt_word_line1_from_top",
        "amt_word_line1_from_left",
        "amt_word_line1_char_count",
        "amt_word_line2_from_top",
        "amt_word_line2_from_left",
        "amt_word_line2_char_count",
        "amt_figure_from_top",
        "amt_figure_from_left",
        "company_name_required",
        "comp_name_from_top",
        "comp_name_from_left",
        "comp_name_char_count",
        "tds_print_required",
        "tds_from_top",
        "tds_from_left",
        "tds_char_count",
        "sign1_required",
        "print_in_sign1",
        "sign1_from_top",
        "sign1_from_left",
        "sign2_required",
        "print_in_sign2",
        "sign2_from_top",
        "sign2_from_left",
        "sign3_required",
        "print_in_sign3",
        "sign3_from_top",
        "sign3_from_left",
        "date_font",
        "name_font",
        "amt_word_line1_font",
        "amt_figure_font",
        "tds_figure_font",
        "amt_word_line2_font",
        "show_star",
    )

    def _cheque_setting_row_to_dict(self, row: Any) -> dict[str, object]:
        item = dict(row)
        settings = json.loads(str(item.pop("settings_json", "{}") or "{}"))
        for key, value in settings.items():
            if key not in item:
                item[key] = value
        return item

    def list_cheque_print_settings(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT cheque_setting_id, bank_name, settings_json
                FROM cheque_print_setting
                WHERE is_deleted = 0
                ORDER BY bank_name COLLATE NOCASE
                """
            ).fetchall()
        return [self._cheque_setting_row_to_dict(row) for row in rows]

    def get_cheque_print_setting(self, setting_key: str) -> dict[str, object]:
        clean = str(setting_key or "").strip()
        if not clean:
            raise ValidationError("Cheque print setting is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT cheque_setting_id, bank_name, settings_json
                FROM cheque_print_setting
                WHERE is_deleted = 0
                  AND (cheque_setting_id = ? OR bank_name = ? COLLATE NOCASE)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
        if row is None:
            raise ValidationError("Cheque print setting not found")
        return self._cheque_setting_row_to_dict(row)

    def save_cheque_print_setting(self, payload: dict[str, Any]) -> dict[str, object]:
        setting_id = str(payload.get("cheque_setting_id") or uuid.uuid4())
        bank_name = str(payload.get("bank_name", "")).strip()
        if not bank_name:
            raise ValidationError("Bank name is required")
        settings = {
            key: payload.get(key)
            for key in self._CHEQUE_PRINT_SETTING_KEYS
            if key in payload
        }
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            duplicate = connection.execute(
                """
                SELECT cheque_setting_id FROM cheque_print_setting
                WHERE is_deleted = 0
                  AND bank_name = ? COLLATE NOCASE
                  AND cheque_setting_id != ?
                LIMIT 1
                """,
                (bank_name, setting_id),
            ).fetchone()
            if duplicate is not None:
                raise ValidationError("Cheque print setting already exists for this bank")
            connection.execute(
                """
                INSERT INTO cheque_print_setting(
                    cheque_setting_id, bank_name, settings_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cheque_setting_id) DO UPDATE SET
                    bank_name = excluded.bank_name,
                    settings_json = excluded.settings_json,
                    updated_at = excluded.updated_at
                """,
                (
                    setting_id,
                    bank_name,
                    json.dumps(settings, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_cheque_print_setting(setting_id)

    def delete_cheque_print_setting(self, setting_key: str) -> dict[str, object]:
        clean = str(setting_key or "").strip()
        if not clean:
            raise ValidationError("Cheque print setting is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT cheque_setting_id FROM cheque_print_setting
                WHERE is_deleted = 0
                  AND (cheque_setting_id = ? OR bank_name = ? COLLATE NOCASE)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
            if row is None:
                raise ValidationError("Cheque print setting not found")
            setting_id = str(row["cheque_setting_id"])
            connection.execute(
                """
                UPDATE cheque_print_setting
                SET is_deleted = 1, updated_at = ?
                WHERE cheque_setting_id = ? AND is_deleted = 0
                """,
                (timestamp, setting_id),
            )
        return {"cheque_setting_id": setting_id, "deleted": True}

    _I_FORM_EXPENSE_NAMES: tuple[str, ...] = (
        "J Form Exp - 1",
        "J Form Exp - 2",
        "I Form Labour",
        "I Form Loading",
        "I Form Stiching",
        "I Form Gaushala",
        "I Form - 5",
        "I Form - 6",
        "I Form - 7",
        "Labour Division Exp - 1",
        "Labour Division Exp - 2",
        "Labour Division Exp - 3",
        "Labour Division Exp - 4",
        "Labour Division Exp - 5",
    )

    def _default_i_form_expense_lines(self) -> list[dict[str, object]]:
        return [
            {
                "expense_name": name,
                "display_name": "",
                "rate": 0,
                "rate_on": "A",
                "account_name": "",
                "round_off": "N",
            }
            for name in self._I_FORM_EXPENSE_NAMES
        ]

    def _merge_i_form_lines(self, saved: list[dict[str, object]]) -> list[dict[str, object]]:
        by_name = {
            str(row.get("expense_name", "")): row
            for row in saved
            if str(row.get("expense_name", "")).strip()
        }
        merged: list[dict[str, object]] = []
        for name in self._I_FORM_EXPENSE_NAMES:
            row = by_name.get(name, {})
            merged.append(
                {
                    "expense_name": name,
                    "display_name": str(row.get("display_name", "")).strip(),
                    "rate": float(row.get("rate") or 0),
                    "rate_on": str(row.get("rate_on", "A") or "A"),
                    "account_name": str(row.get("account_name", "")).strip(),
                    "round_off": str(row.get("round_off", "N") or "N"),
                }
            )
        return merged

    def list_i_form_expense_defines(
        self, commodity_id: str = ""
    ) -> list[dict[str, object]]:
        clean = str(commodity_id or "").strip()
        with self.databases.connect(self.database_path) as connection:
            if clean:
                rows = connection.execute(
                    """
                    SELECT d.define_id, d.commodity_id, d.effective_date, d.dami, d.dami_on,
                        d.dami_r_off, d.bonus, d.bonus_r_off, d.rdf_kkf_percent, d.rdf_r_off,
                        d.mkt_percent, d.mkt_r_off, d.lines_json, c.name AS item_name
                    FROM i_form_expense_define d
                    JOIN commodity c ON c.commodity_id = d.commodity_id
                    WHERE d.is_deleted = 0 AND d.commodity_id = ?
                    ORDER BY d.effective_date DESC
                    """,
                    (clean,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT d.define_id, d.commodity_id, d.effective_date, d.dami, d.dami_on,
                        d.dami_r_off, d.bonus, d.bonus_r_off, d.rdf_kkf_percent, d.rdf_r_off,
                        d.mkt_percent, d.mkt_r_off, d.lines_json, c.name AS item_name
                    FROM i_form_expense_define d
                    JOIN commodity c ON c.commodity_id = d.commodity_id
                    WHERE d.is_deleted = 0
                    ORDER BY c.name COLLATE NOCASE, d.effective_date DESC
                    """
                ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            saved = json.loads(str(item.pop("lines_json") or "[]"))
            item["lines"] = self._merge_i_form_lines(saved)
            result.append(item)
        return result

    def get_i_form_expense_define(
        self, commodity_id: str, effective_date: str
    ) -> dict[str, object]:
        clean_item = str(commodity_id or "").strip()
        clean_date = str(effective_date or "").strip()
        if not clean_item or not clean_date:
            raise ValidationError("Item and date are required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT define_id, commodity_id, effective_date, dami, dami_on, dami_r_off,
                    bonus, bonus_r_off, rdf_kkf_percent, rdf_r_off, mkt_percent, mkt_r_off,
                    lines_json
                FROM i_form_expense_define
                WHERE is_deleted = 0
                  AND commodity_id = ? AND effective_date = ?
                LIMIT 1
                """,
                (clean_item, clean_date),
            ).fetchone()
        if row is None:
            return {
                "define_id": "",
                "commodity_id": clean_item,
                "effective_date": clean_date,
                "dami": "",
                "dami_on": "A",
                "dami_r_off": "N",
                "bonus": "",
                "bonus_r_off": "N",
                "rdf_kkf_percent": "",
                "rdf_r_off": "N",
                "mkt_percent": "",
                "mkt_r_off": "N",
                "lines": self._default_i_form_expense_lines(),
            }
        item = dict(row)
        saved = json.loads(str(item.pop("lines_json") or "[]"))
        item["lines"] = self._merge_i_form_lines(saved)
        return item

    def save_i_form_expense_define(self, payload: dict[str, Any]) -> dict[str, object]:
        commodity_id = str(payload.get("commodity_id") or "").strip()
        effective_date = str(payload.get("effective_date") or "").strip()
        if not commodity_id or not effective_date:
            raise ValidationError("Item and date are required")
        lines = payload.get("lines", [])
        if not isinstance(lines, list):
            raise ValidationError("Expense lines must be a list")
        timestamp = utc_now()
        merged_lines = self._merge_i_form_lines(lines)
        with self.databases.connect(self.database_path) as connection:
            existing = connection.execute(
                """
                SELECT define_id FROM i_form_expense_define
                WHERE is_deleted = 0 AND commodity_id = ? AND effective_date = ?
                LIMIT 1
                """,
                (commodity_id, effective_date),
            ).fetchone()
            define_id = str(
                payload.get("define_id")
                or (existing["define_id"] if existing else "")
                or uuid.uuid4()
            )
            if existing:
                connection.execute(
                    """
                    UPDATE i_form_expense_define SET
                        dami = ?, dami_on = ?, dami_r_off = ?,
                        bonus = ?, bonus_r_off = ?,
                        rdf_kkf_percent = ?, rdf_r_off = ?,
                        mkt_percent = ?, mkt_r_off = ?,
                        lines_json = ?, updated_at = ?
                    WHERE define_id = ? AND is_deleted = 0
                    """,
                    (
                        str(payload.get("dami", "")).strip() or None,
                        str(payload.get("dami_on", "A")).strip() or "A",
                        str(payload.get("dami_r_off", "N")).strip() or "N",
                        str(payload.get("bonus", "")).strip() or None,
                        str(payload.get("bonus_r_off", "N")).strip() or "N",
                        str(payload.get("rdf_kkf_percent", "")).strip() or None,
                        str(payload.get("rdf_r_off", "N")).strip() or "N",
                        str(payload.get("mkt_percent", "")).strip() or None,
                        str(payload.get("mkt_r_off", "N")).strip() or "N",
                        json.dumps(merged_lines, sort_keys=True),
                        timestamp,
                        define_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO i_form_expense_define(
                        define_id, commodity_id, effective_date, dami, dami_on, dami_r_off,
                        bonus, bonus_r_off, rdf_kkf_percent, rdf_r_off, mkt_percent, mkt_r_off,
                        lines_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        define_id,
                        commodity_id,
                        effective_date,
                        str(payload.get("dami", "")).strip() or None,
                        str(payload.get("dami_on", "A")).strip() or "A",
                        str(payload.get("dami_r_off", "N")).strip() or "N",
                        str(payload.get("bonus", "")).strip() or None,
                        str(payload.get("bonus_r_off", "N")).strip() or "N",
                        str(payload.get("rdf_kkf_percent", "")).strip() or None,
                        str(payload.get("rdf_r_off", "N")).strip() or "N",
                        str(payload.get("mkt_percent", "")).strip() or None,
                        str(payload.get("mkt_r_off", "N")).strip() or "N",
                        json.dumps(merged_lines, sort_keys=True),
                        timestamp,
                        timestamp,
                    ),
                )
        return {
            "define_id": define_id,
            "commodity_id": commodity_id,
            "effective_date": effective_date,
        }

    def delete_i_form_expense_define(self, define_id: str) -> dict[str, object]:
        clean = str(define_id or "").strip()
        if not clean:
            raise ValidationError("Record is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            updated = connection.execute(
                """
                UPDATE i_form_expense_define
                SET is_deleted = 1, updated_at = ?
                WHERE define_id = ? AND is_deleted = 0
                """,
                (timestamp, clean),
            )
            if updated.rowcount == 0:
                raise ValidationError("I Form expense define not found")
        return {"define_id": clean, "deleted": True}

    def list_items(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT commodity_id, name, variety, hsn_code, item_metadata_json
                FROM commodity
                WHERE is_deleted = 0
                ORDER BY name COLLATE NOCASE, variety COLLATE NOCASE
                """
            ).fetchall()
        return [self._item_row_to_dict(row) for row in rows]

    def list_trading_accounts(self) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT trading_account_id, trading_code, name, profit_loss_account,
                    raw_commodity_ids_json, finished_commodity_ids_json
                FROM trading_account
                WHERE is_deleted = 0
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            item["raw_commodity_ids"] = json.loads(
                str(item.pop("raw_commodity_ids_json") or "[]")
            )
            item["finished_commodity_ids"] = json.loads(
                str(item.pop("finished_commodity_ids_json") or "[]")
            )
            result.append(item)
        return result

    def get_trading_account(self, trading_key: str) -> dict[str, object]:
        clean = str(trading_key or "").strip()
        if not clean:
            raise ValidationError("Trading account is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT trading_account_id, trading_code, name, profit_loss_account,
                    raw_commodity_ids_json, finished_commodity_ids_json
                FROM trading_account
                WHERE is_deleted = 0
                  AND (trading_account_id = ? OR trading_code = ?)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
        if row is None:
            raise ValidationError("Trading account not found")
        item = dict(row)
        item["raw_commodity_ids"] = json.loads(
            str(item.pop("raw_commodity_ids_json") or "[]")
        )
        item["finished_commodity_ids"] = json.loads(
            str(item.pop("finished_commodity_ids_json") or "[]")
        )
        return item

    def save_trading_account(self, payload: dict[str, Any]) -> dict[str, object]:
        trading_account_id = str(payload.get("trading_account_id") or uuid.uuid4())
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValidationError("Trading account name is required")
        raw_ids = payload.get("raw_commodity_ids") or []
        finished_ids = payload.get("finished_commodity_ids") or []
        if not isinstance(raw_ids, list) or not isinstance(finished_ids, list):
            raise ValidationError("Item selections must be lists")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO trading_account(
                    trading_account_id, trading_code, name, profit_loss_account,
                    raw_commodity_ids_json, finished_commodity_ids_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trading_account_id) DO UPDATE SET
                    trading_code = excluded.trading_code,
                    name = excluded.name,
                    profit_loss_account = excluded.profit_loss_account,
                    raw_commodity_ids_json = excluded.raw_commodity_ids_json,
                    finished_commodity_ids_json = excluded.finished_commodity_ids_json,
                    updated_at = excluded.updated_at
                """,
                (
                    trading_account_id,
                    str(payload.get("trading_code", "")).strip() or None,
                    name,
                    str(payload.get("profit_loss_account", "")).strip() or None,
                    json.dumps([str(x) for x in raw_ids], sort_keys=True),
                    json.dumps([str(x) for x in finished_ids], sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        return {"trading_account_id": trading_account_id, "name": name}

    def delete_trading_account(self, trading_key: str) -> dict[str, object]:
        clean = str(trading_key or "").strip()
        if not clean:
            raise ValidationError("Trading account is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT trading_account_id FROM trading_account
                WHERE is_deleted = 0 AND (trading_account_id = ? OR trading_code = ?)
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
            if row is None:
                raise ValidationError("Trading account not found")
            trading_account_id = str(row["trading_account_id"])
            connection.execute(
                """
                UPDATE trading_account
                SET is_deleted = 1, updated_at = ?
                WHERE trading_account_id = ? AND is_deleted = 0
                """,
                (timestamp, trading_account_id),
            )
        return {"trading_account_id": trading_account_id, "deleted": True}

    _ITEM_METADATA_KEYS: tuple[str, ...] = (
        "item_code",
        "item_group",
        "sub_group",
        "unit",
        "rate_per",
        "bardana_item",
        "item_type",
        "having_yield",
        "paddy",
        "exempted",
        "market_fee",
        "market_pct",
        "rdf_fee_pct",
        "grace_days",
        "bharti",
        "bardana_req",
        "tds_required",
        "stockable",
        "gst_type",
        "gst_type_h_form",
        "uqc",
        "text_print_nug",
        "text_print_wt",
        "sale_ser",
        "k_form_reg",
        "rcm_purchase",
        "rcm_inv_req",
        "blocked_itc",
        "gross_tare_wt_req",
        "bal_stock_qty_msg",
    )

    def _item_row_to_dict(self, row: Any) -> dict[str, object]:
        item = dict(row)
        meta = json.loads(str(item.pop("item_metadata_json", "{}") or "{}"))
        for key, value in meta.items():
            if key not in item:
                item[key] = value
        return item

    def get_item(self, item_key: str) -> dict[str, object]:
        clean = str(item_key or "").strip()
        if not clean:
            raise ValidationError("Item is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT commodity_id, name, variety, hsn_code, item_metadata_json
                FROM commodity
                WHERE is_deleted = 0
                  AND (
                    commodity_id = ?
                    OR name = ? COLLATE NOCASE
                    OR json_extract(item_metadata_json, '$.item_code') = ?
                  )
                LIMIT 1
                """,
                (clean, clean, clean),
            ).fetchone()
        if row is None:
            raise ValidationError("Item not found")
        return self._item_row_to_dict(row)

    def delete_item(self, item_key: str) -> dict[str, object]:
        clean = str(item_key or "").strip()
        if not clean:
            raise ValidationError("Item is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT commodity_id FROM commodity
                WHERE is_deleted = 0
                  AND (
                    commodity_id = ?
                    OR json_extract(item_metadata_json, '$.item_code') = ?
                  )
                LIMIT 1
                """,
                (clean, clean),
            ).fetchone()
            if row is None:
                raise ValidationError("Item not found")
            commodity_id = str(row["commodity_id"])
            connection.execute(
                """
                UPDATE commodity
                SET is_deleted = 1, updated_at = ?, version = version + 1
                WHERE commodity_id = ? AND is_deleted = 0
                """,
                (timestamp, commodity_id),
            )
        return {"commodity_id": commodity_id, "deleted": True}

    def save_item(self, payload: dict[str, Any]) -> dict[str, object]:
        commodity_id = payload.get("commodity_id")
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValidationError("Item name is required")
        exempt = str(payload.get("exempted", "No")).strip().lower() in {"y", "yes"}
        hsn = str(payload.get("hsn_code", "")).strip()
        validate_hsn(hsn, exempt=exempt)
        uqc_raw = str(payload.get("uqc", "") or payload.get("unit", "")).strip()
        uqc = validate_uqc(uqc_raw, required=not exempt)
        metadata = {
            key: payload.get(key)
            for key in self._ITEM_METADATA_KEYS
            if key in payload
        }
        metadata["uqc"] = uqc
        timestamp = utc_now()
        if commodity_id:
            with self.databases.connect(self.database_path) as connection:
                connection.execute(
                    """
                    UPDATE commodity
                    SET name = ?, variety = ?, hsn_code = ?, uqc = ?, item_metadata_json = ?,
                        version = version + 1, updated_at = ?
                    WHERE commodity_id = ? AND is_deleted = 0
                    """,
                    (
                        name,
                        str(payload.get("variety", "")).strip(),
                        hsn or None,
                        uqc or None,
                        json.dumps(metadata, sort_keys=True),
                        timestamp,
                        str(commodity_id),
                    ),
                )
            return self.get_item(str(commodity_id))
        created = self.accounting.create_commodity(
            name,
            variety=str(payload.get("variety", "")),
            hsn_code=hsn,
            quantity_scale=int(payload.get("quantity_scale", 3)),
            standard_bag_weight_scaled=payload.get("standard_bag_weight_scaled"),
        )
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE commodity
                SET item_metadata_json = ?, uqc = ?
                WHERE commodity_id = ?
                """,
                (
                    json.dumps(metadata, sort_keys=True),
                    uqc or None,
                    str(created["commodity_id"]),
                ),
            )
        return self.get_item(str(created["commodity_id"]))

    def save_account_master(self, payload: dict[str, Any]) -> dict[str, object]:
        account_id = payload.get("account_id")
        name = str(payload.get("name", "")).strip()
        account_type = str(payload.get("account_type", "party")).strip()
        if not name:
            raise ValidationError("Account name is required")
        metadata = {
            key: payload.get(key)
            for key in _ACCOUNT_METADATA_KEYS
            if key in payload
        }
        timestamp = utc_now()
        party_id = str(payload.get("party_id") or "").strip()
        party_type = str(payload.get("party_type", "farmer")).strip() or "farmer"
        address = str(payload.get("address", "")).strip()
        if account_id:
            with self.databases.connect(self.database_path) as connection:
                connection.execute(
                    """
                    UPDATE account
                    SET name = ?, account_type = ?, metadata_json = ?,
                        opening_debit_paise = ?, opening_credit_paise = ?,
                        version = version + 1, updated_at = ?
                    WHERE account_id = ? AND is_deleted = 0
                    """,
                    (
                        name,
                        account_type,
                        json.dumps(metadata, sort_keys=True),
                        int(payload.get("opening_debit_paise", 0)),
                        int(payload.get("opening_credit_paise", 0)),
                        timestamp,
                        str(account_id),
                    ),
                )
                if party_id:
                    connection.execute(
                        """
                        UPDATE party
                        SET name = ?, party_type = ?, gstin = ?, pan = ?, address = ?,
                            city = ?, phone = ?, father_name = ?,
                            version = version + 1, updated_at = ?
                        WHERE party_id = ? AND is_deleted = 0
                        """,
                        (
                            name,
                            party_type,
                            str(payload.get("gstin", "")).strip() or None,
                            str(payload.get("pan", "")).strip() or None,
                            address or None,
                            str(payload.get("city", "")).strip() or None,
                            str(payload.get("mobile1", payload.get("phone", ""))).strip() or None,
                            str(payload.get("contact_person", payload.get("father_name", ""))).strip()
                            or None,
                            timestamp,
                            party_id,
                        ),
                    )
            return {"account_id": str(account_id), "name": name, "party_id": party_id or None}
        created = self.accounting.create_account(name, account_type)
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE account
                SET metadata_json = ?, opening_debit_paise = ?, opening_credit_paise = ?
                WHERE account_id = ?
                """,
                (
                    json.dumps(metadata, sort_keys=True),
                    int(payload.get("opening_debit_paise", 0)),
                    int(payload.get("opening_credit_paise", 0)),
                    created["account_id"],
                ),
            )
        party = self.accounting.create_party(
            name,
            party_type,
            gstin=str(payload.get("gstin", "")),
            pan=str(payload.get("pan", "")),
            address=address,
            city=str(payload.get("city", "")),
            phone=str(payload.get("mobile1", payload.get("phone", ""))),
            father_name=str(payload.get("contact_person", payload.get("father_name", ""))),
            account_id=created["account_id"],
        )
        return {**created, "party_id": party["party_id"]}

    def delete_account_master(self, account_id: str) -> dict[str, object]:
        clean = str(account_id or "").strip()
        if not clean:
            raise ValidationError("Account is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            updated = connection.execute(
                """
                UPDATE account SET is_deleted = 1, updated_at = ?
                WHERE account_id = ? AND is_deleted = 0
                """,
                (timestamp, clean),
            )
            if updated.rowcount == 0:
                raise ValidationError("Account not found")
            connection.execute(
                """
                UPDATE party SET is_deleted = 1, updated_at = ?
                WHERE account_id = ? AND is_deleted = 0
                """,
                (timestamp, clean),
            )
        return {"account_id": clean, "deleted": True}

    def _account_master_record(self, data: dict[str, object]) -> dict[str, object]:
        metadata = _parse_account_metadata(data.get("metadata_json"))
        opening_dr = int(data.get("opening_debit_paise") or 0)
        opening_cr = int(data.get("opening_credit_paise") or 0)
        side, balance = _opening_side_label(opening_dr, opening_cr)
        address_raw = str(data.get("address") or "")
        address_lines = [line for line in address_raw.split("\n") if line.strip()]
        while len(address_lines) < 3:
            address_lines.append("")
        if metadata.get("address_line2"):
            address_lines[1] = str(metadata["address_line2"])
        if metadata.get("address_line3"):
            address_lines[2] = str(metadata["address_line3"])
        record: dict[str, object] = {
            "party_id": str(data.get("party_id") or ""),
            "account_id": str(data.get("account_id") or ""),
            "name": str(data.get("name") or data.get("account_name") or ""),
            "party_type": str(data.get("party_type") or "farmer"),
            "gstin": str(data.get("gstin") or ""),
            "pan": str(data.get("pan") or ""),
            "address": address_lines[0],
            "address_line2": address_lines[1],
            "address_line3": address_lines[2],
            "city": str(data.get("city") or ""),
            "phone": str(metadata.get("phone") or data.get("phone") or ""),
            "mobile1": str(metadata.get("mobile1") or data.get("phone") or ""),
            "opening_side": side,
            "opening_balance": balance,
        }
        for key in _ACCOUNT_METADATA_KEYS:
            if key in metadata and metadata[key] is not None:
                record[key] = metadata[key]
        record["contact_person"] = str(
            metadata.get("contact_person") or data.get("father_name") or "",
        )
        record["party_gst_type"] = str(
            metadata.get("party_gst_type") or metadata.get("gst_type") or "Unregistered",
        )
        record["account_code"] = str(metadata.get("account_code") or "")
        return record

    def get_account_master(self, account_id: str) -> dict[str, object]:
        clean = str(account_id or "").strip()
        if not clean:
            raise ValidationError("Account is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT p.party_id, p.name, p.party_type, p.gstin, p.pan, p.address, p.city,
                    p.phone, p.father_name, p.account_id,
                    a.name AS account_name, a.metadata_json,
                    a.opening_debit_paise, a.opening_credit_paise
                FROM account a
                LEFT JOIN party p ON p.account_id = a.account_id AND p.is_deleted = 0
                WHERE a.account_id = ? AND a.is_deleted = 0
                LIMIT 1
                """,
                (clean,),
            ).fetchone()
        if row is None:
            raise ValidationError("Account not found")
        return self._account_master_record(dict(row))

    def get_party_master(self, party_id: str) -> dict[str, object]:
        clean = str(party_id or "").strip()
        if not clean:
            raise ValidationError("Party is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT p.party_id, p.name, p.party_type, p.gstin, p.pan, p.address, p.city,
                    p.phone, p.father_name, p.account_id,
                    a.name AS account_name, a.metadata_json,
                    a.opening_debit_paise, a.opening_credit_paise
                FROM party p
                LEFT JOIN account a ON a.account_id = p.account_id AND a.is_deleted = 0
                WHERE p.party_id = ? AND p.is_deleted = 0
                """,
                (clean,),
            ).fetchone()
        if row is None:
            raise ValidationError("Party not found")
        return self._account_master_record(dict(row))

    def _parse_stock_entry_lines(self, raw: Any) -> list[dict[str, object]]:
        if not isinstance(raw, list):
            return []
        lines: list[dict[str, object]] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            item_name = str(row.get("item_name", "")).strip()
            commodity_id = str(row.get("commodity_id", "")).strip()
            if not item_name and not commodity_id:
                continue
            lines.append(
                {
                    "line_id": str(row.get("line_id") or uuid.uuid4()),
                    "commodity_id": commodity_id or None,
                    "item_name": item_name or None,
                    "unit": str(row.get("unit", "")).strip() or None,
                    "account_id": str(row.get("account_id", "")).strip() or None,
                    "account_name": str(row.get("account_name", "")).strip() or None,
                    "qty": str(row.get("qty", "")).strip() or None,
                    "weight": str(row.get("weight", "")).strip() or None,
                    "rate": str(row.get("rate", "")).strip() or None,
                    "amount": str(row.get("amount", "")).strip() or None,
                    "mm": str(row.get("mm", "")).strip() or None,
                }
            )
        return lines

    def _stock_entry_row_to_dict(self, row: Any) -> dict[str, object]:
        item = dict(row)
        item["lines"] = self._parse_stock_entry_lines(
            json.loads(str(item.pop("lines_json", "[]") or "[]"))
        )
        item["show_opening"] = bool(int(item.get("show_opening") or 0))
        return item

    def list_stock_entries(
        self, financial_year_id: str, entry_kind: str = ""
    ) -> list[dict[str, object]]:
        clean_kind = str(entry_kind or "").strip().lower()
        with self.databases.connect(self.database_path) as connection:
            if clean_kind in {"opening", "closing"}:
                rows = connection.execute(
                    """
                    SELECT stock_entry_id, financial_year_id, entry_kind, entry_date,
                        search_item, show_opening, filter1, filter2, filter3, filter4, lines_json
                    FROM stock_entry_master
                    WHERE is_deleted = 0
                      AND financial_year_id = ?
                      AND entry_kind = ?
                    ORDER BY entry_date DESC
                    """,
                    (financial_year_id, clean_kind),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT stock_entry_id, financial_year_id, entry_kind, entry_date,
                        search_item, show_opening, filter1, filter2, filter3, filter4, lines_json
                    FROM stock_entry_master
                    WHERE is_deleted = 0 AND financial_year_id = ?
                    ORDER BY entry_kind, entry_date DESC
                    """,
                    (financial_year_id,),
                ).fetchall()
        return [self._stock_entry_row_to_dict(row) for row in rows]

    def get_stock_entry(
        self,
        financial_year_id: str,
        stock_entry_key: str,
        *,
        entry_kind: str = "",
        entry_date: str = "",
        search_item: str = "",
    ) -> dict[str, object]:
        clean = str(stock_entry_key or "").strip()
        clean_kind = str(entry_kind or "").strip().lower()
        clean_date = str(entry_date or "").strip()
        with self.databases.connect(self.database_path) as connection:
            if clean:
                row = connection.execute(
                    """
                    SELECT stock_entry_id, financial_year_id, entry_kind, entry_date,
                        search_item, show_opening, filter1, filter2, filter3, filter4, lines_json
                    FROM stock_entry_master
                    WHERE is_deleted = 0
                      AND financial_year_id = ?
                      AND stock_entry_id = ?
                    LIMIT 1
                    """,
                    (financial_year_id, clean),
                ).fetchone()
            elif clean_kind in {"opening", "closing"} and clean_date:
                row = connection.execute(
                    """
                    SELECT stock_entry_id, financial_year_id, entry_kind, entry_date,
                        search_item, show_opening, filter1, filter2, filter3, filter4, lines_json
                    FROM stock_entry_master
                    WHERE is_deleted = 0
                      AND financial_year_id = ?
                      AND entry_kind = ?
                      AND entry_date = ?
                    LIMIT 1
                    """,
                    (financial_year_id, clean_kind, clean_date),
                ).fetchone()
            else:
                raise ValidationError("Stock entry is required")
        if row is None:
            raise ValidationError("Stock entry not found")
        record = self._stock_entry_row_to_dict(row)
        needle = str(search_item or "").strip().lower()
        if needle:
            lines = record.get("lines", [])
            if isinstance(lines, list):
                record["lines"] = [
                    line
                    for line in lines
                    if needle
                    in " ".join(
                        str(line.get(key, ""))
                        for key in ("item_name", "account_name", "unit")
                    ).lower()
                ]
        return record

    def _sync_opening_stock_lines(
        self, financial_year_id: str, lines: list[dict[str, object]]
    ) -> None:
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                "DELETE FROM opening_stock WHERE financial_year_id = ?",
                (financial_year_id,),
            )
            for line in lines:
                commodity_id = str(line.get("commodity_id") or "").strip()
                if not commodity_id:
                    continue
                qty = float(str(line.get("qty") or "0").replace(",", "") or 0)
                weight = float(str(line.get("weight") or "0").replace(",", "") or 0)
                rate = float(str(line.get("rate") or "0").replace(",", "") or 0)
                amount = float(str(line.get("amount") or "0").replace(",", "") or 0)
                if not amount and weight and rate:
                    amount = weight * rate
                row_id = str(line.get("line_id") or uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO opening_stock(
                        opening_stock_id, financial_year_id, commodity_id, unit, bags,
                        quantity_scaled, rate_paise, amount_paise, account_id, account_name,
                        entry_mm, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row_id,
                        financial_year_id,
                        commodity_id,
                        str(line.get("unit") or "").strip() or None,
                        int(qty),
                        int(round(weight * 1000)),
                        int(round(rate * 100)),
                        int(round(amount * 100)),
                        str(line.get("account_id") or "").strip() or None,
                        str(line.get("account_name") or "").strip() or None,
                        str(line.get("mm") or "").strip() or None,
                        timestamp,
                        timestamp,
                    ),
                )

    def save_stock_entry_master(
        self, financial_year_id: str, payload: dict[str, Any]
    ) -> dict[str, object]:
        entry_kind = str(payload.get("entry_kind", "")).strip().lower()
        if entry_kind not in {"opening", "closing"}:
            raise ValidationError("Stock entry kind must be opening or closing")
        entry_date = str(payload.get("entry_date", "")).strip()
        if not entry_date:
            raise ValidationError("Entry date is required")
        lines = self._parse_stock_entry_lines(payload.get("lines", []))
        stock_entry_id = str(payload.get("stock_entry_id") or "").strip()
        show_opening = 1 if payload.get("show_opening") else 0
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            if not stock_entry_id:
                existing = connection.execute(
                    """
                    SELECT stock_entry_id FROM stock_entry_master
                    WHERE is_deleted = 0
                      AND financial_year_id = ?
                      AND entry_kind = ?
                      AND entry_date = ?
                    LIMIT 1
                    """,
                    (financial_year_id, entry_kind, entry_date),
                ).fetchone()
                stock_entry_id = (
                    str(existing["stock_entry_id"])
                    if existing is not None
                    else str(uuid.uuid4())
                )
            connection.execute(
                """
                INSERT INTO stock_entry_master(
                    stock_entry_id, financial_year_id, entry_kind, entry_date, search_item,
                    show_opening, filter1, filter2, filter3, filter4, lines_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stock_entry_id) DO UPDATE SET
                    entry_date = excluded.entry_date,
                    search_item = excluded.search_item,
                    show_opening = excluded.show_opening,
                    filter1 = excluded.filter1,
                    filter2 = excluded.filter2,
                    filter3 = excluded.filter3,
                    filter4 = excluded.filter4,
                    lines_json = excluded.lines_json,
                    updated_at = excluded.updated_at
                """,
                (
                    stock_entry_id,
                    financial_year_id,
                    entry_kind,
                    entry_date,
                    str(payload.get("search_item", "")).strip() or None,
                    show_opening,
                    str(payload.get("filter1", "")).strip() or None,
                    str(payload.get("filter2", "")).strip() or None,
                    str(payload.get("filter3", "")).strip() or None,
                    str(payload.get("filter4", "")).strip() or None,
                    json.dumps(lines, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
        if entry_kind == "opening":
            self._sync_opening_stock_lines(financial_year_id, lines)
        return self.get_stock_entry(financial_year_id, stock_entry_id)

    def delete_stock_entry_master(
        self, financial_year_id: str, stock_entry_key: str
    ) -> dict[str, object]:
        clean = str(stock_entry_key or "").strip()
        if not clean:
            raise ValidationError("Stock entry is required")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT stock_entry_id, entry_kind FROM stock_entry_master
                WHERE is_deleted = 0
                  AND financial_year_id = ?
                  AND stock_entry_id = ?
                LIMIT 1
                """,
                (financial_year_id, clean),
            ).fetchone()
            if row is None:
                raise ValidationError("Stock entry not found")
            entry_kind = str(row["entry_kind"])
            stock_entry_id = str(row["stock_entry_id"])
            connection.execute(
                """
                UPDATE stock_entry_master
                SET is_deleted = 1, updated_at = ?
                WHERE stock_entry_id = ? AND is_deleted = 0
                """,
                (timestamp, stock_entry_id),
            )
            if entry_kind == "opening":
                connection.execute(
                    "DELETE FROM opening_stock WHERE financial_year_id = ?",
                    (financial_year_id,),
                )
        return {"stock_entry_id": stock_entry_id, "deleted": True}

    def save_opening_stock(self, financial_year_id: str, payload: dict[str, Any]) -> dict[str, object]:
        commodity_id = str(payload.get("commodity_id", "")).strip()
        if not commodity_id:
            raise ValidationError("Item is required for opening stock")
        row_id = str(payload.get("opening_stock_id") or uuid.uuid4())
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO opening_stock(
                    opening_stock_id, financial_year_id, commodity_id, unit, bags,
                    quantity_scaled, rate_paise, amount_paise, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(opening_stock_id) DO UPDATE SET
                    commodity_id = excluded.commodity_id,
                    unit = excluded.unit,
                    bags = excluded.bags,
                    quantity_scaled = excluded.quantity_scaled,
                    rate_paise = excluded.rate_paise,
                    amount_paise = excluded.amount_paise,
                    updated_at = excluded.updated_at
                """,
                (
                    row_id,
                    financial_year_id,
                    commodity_id,
                    str(payload.get("unit", "")).strip() or None,
                    int(payload.get("bags", 0)),
                    int(payload.get("quantity_scaled", 0)),
                    int(payload.get("rate_paise", 0)),
                    int(payload.get("amount_paise", 0)),
                    timestamp,
                    timestamp,
                ),
            )
        return {"opening_stock_id": row_id}
