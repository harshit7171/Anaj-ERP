"""Master data, financial-year and double-entry accounting services."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from .database import DatabaseManager
from .database import utc_now
from .domain import FinancialYear
from .domain import LedgerLine
from .domain import validate_balanced
from .errors import StateError
from .errors import ValidationError
from .access_policy import current_access
from .mandi_business import evaluate_backdate_policy
from .mandi_business import merge_company_settings
from .mandi_business import verify_manager_pin
ACCOUNT_TYPES = {
    "asset",
    "liability",
    "income",
    "expense",
    "capital",
    "cash",
    "bank",
    "party",
}
PARTY_TYPES = {
    "customer",
    "supplier",
    "farmer",
    "purchaser",
    "commission_agent",
    "transporter",
}
SEARCH_TABLES = {
    "account": ("account_id", "name", "account"),
    "party": (
        "party_id",
        "(name || CASE WHEN related_name IS NOT NULL AND related_name != '' "
        "THEN ' - ' || related_name ELSE '' END)",
        "party",
    ),
    "commodity": ("commodity_id", "name", "commodity"),
}


class AccountingService:
    """Operate on one company's masters, years and ledger."""

    def __init__(
        self,
        databases: DatabaseManager,
        company_id: str,
    ) -> None:
        """Resolve the company database for accounting operations."""
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)

    def add_financial_year(self, start_year: int) -> dict[str, object]:
        """Create another April-March financial year."""
        year = FinancialYear(start_year)
        year_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO financial_year(
                    financial_year_id, start_year, starts_on, ends_on,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    year_id,
                    year.start_year,
                    year.starts_on.isoformat(),
                    year.ends_on.isoformat(),
                    timestamp,
                    timestamp,
                ),
            )
            self._audit(
                connection,
                year_id,
                "financial_year",
                year_id,
                "create",
                {"start_year": start_year},
            )
        return {
            "financial_year_id": year_id,
            "start_year": start_year,
            "label": year.label,
            "is_locked": False,
        }

    def rollover_financial_year(
        self,
        *,
        source_financial_year_id: str,
        target_start_year: int,
        lock_source: bool = True,
        lock_reason: str = "Year-end rollover",
    ) -> dict[str, object]:
        """Create the next FY and carry forward account closing balances as opening."""
        target = self.add_financial_year(target_start_year)
        target_id = str(target["financial_year_id"])
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT a.account_id,
                    a.opening_debit_paise, a.opening_credit_paise,
                    COALESCE(SUM(vl.debit_paise), 0) AS debit_paise,
                    COALESCE(SUM(vl.credit_paise), 0) AS credit_paise
                FROM account a
                LEFT JOIN voucher_line vl ON vl.account_id = a.account_id
                LEFT JOIN voucher v ON v.voucher_id = vl.voucher_id
                    AND v.financial_year_id = ? AND v.status IN ('posted', 'reversed')
                WHERE a.is_deleted = 0
                GROUP BY a.account_id, a.opening_debit_paise, a.opening_credit_paise
                """,
                (source_financial_year_id,),
            ).fetchall()
            carried = 0
            for row in rows:
                opening = int(row["opening_debit_paise"]) - int(row["opening_credit_paise"])
                movement = int(row["debit_paise"]) - int(row["credit_paise"])
                closing = opening + movement
                if closing == 0:
                    continue
                connection.execute(
                    """
                    UPDATE account
                    SET opening_debit_paise = ?, opening_credit_paise = ?, updated_at = ?
                    WHERE account_id = ?
                    """,
                    (
                        max(closing, 0),
                        max(-closing, 0),
                        timestamp,
                        str(row["account_id"]),
                    ),
                )
                carried += 1
            if lock_source:
                connection.execute(
                    """
                    UPDATE financial_year
                    SET is_locked = 1, lock_reason = ?, locked_at = ?, updated_at = ?
                    WHERE financial_year_id = ?
                    """,
                    (lock_reason, timestamp, timestamp, source_financial_year_id),
                )
        return {
            "target_financial_year_id": target_id,
            "target_label": target["label"],
            "accounts_carried": carried,
            "source_locked": lock_source,
        }

    def set_year_lock(
        self,
        financial_year_id: str,
        locked: bool,
        reason: str,
    ) -> None:
        """Lock or audited-reopen a financial year."""
        clean_reason = reason.strip()
        if not clean_reason:
            raise ValidationError("A reason is required to lock or reopen a year")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            current = connection.execute(
                """
                SELECT version FROM financial_year
                WHERE financial_year_id = ?
                """,
                (financial_year_id,),
            ).fetchone()
            if current is None:
                raise ValidationError("Financial year does not exist")
            base_version = int(current["version"])
            result = connection.execute(
                """
                UPDATE financial_year
                SET is_locked = ?, lock_reason = ?, locked_at = ?,
                    version = version + 1, updated_at = ?
                WHERE financial_year_id = ?
                """,
                (
                    int(locked),
                    clean_reason,
                    timestamp if locked else None,
                    timestamp,
                    financial_year_id,
                ),
            )
            if result.rowcount != 1:
                raise ValidationError("Financial year does not exist")
            self._audit(
                connection,
                financial_year_id,
                "financial_year",
                financial_year_id,
                "lock" if locked else "reopen",
                {"reason": clean_reason},
                reason=clean_reason,
            )

    def create_account(
        self,
        name: str,
        account_type: str,
        financial_year_id: str | None = None,
    ) -> dict[str, str]:
        """Create a ledger account master."""
        clean_name = self._required_text(name, "Account name")
        if account_type not in ACCOUNT_TYPES:
            raise ValidationError("Invalid account type")
        account_id = str(uuid.uuid4())
        timestamp = utc_now()
        payload = {
            "account_id": account_id,
            "name": clean_name,
            "account_type": account_type,
            "financial_year_id": financial_year_id,
        }
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO account(
                    account_id, financial_year_id, name, account_type,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    financial_year_id,
                    clean_name,
                    account_type,
                    timestamp,
                    timestamp,
                ),
            )
            self._audit(
                connection,
                financial_year_id,
                "account",
                account_id,
                "create",
                payload,
            )
        return {"account_id": account_id, "name": clean_name, "account_type": account_type}

    def create_party(
        self,
        name: str,
        party_type: str,
        *,
        gstin: str = "",
        pan: str = "",
        address: str = "",
        city: str = "",
        phone: str = "",
        related_name: str = "",
        father_name: str = "",
        agricultural_group: str = "",
        village_name: str = "",
        credit_limit_paise: int = 0,
        account_id: str | None = None,
    ) -> dict[str, str]:
        """Create a party master used by invoices and vouchers."""
        clean_name = self._required_text(name, "Party name")
        if party_type not in PARTY_TYPES:
            raise ValidationError("Invalid party type")
        if credit_limit_paise < 0:
            raise ValidationError("Credit limit cannot be negative")
        clean_gstin = gstin.strip().upper()
        if clean_gstin and len(clean_gstin) != 15:
            raise ValidationError("GSTIN must contain 15 characters")
        clean_father = father_name.strip() or related_name.strip()
        party_id = str(uuid.uuid4())
        timestamp = utc_now()
        payload = {
            "party_id": party_id,
            "name": clean_name,
            "party_type": party_type,
            "gstin": clean_gstin,
            "pan": pan.strip().upper(),
            "address": address.strip(),
            "city": city.strip(),
            "phone": phone.strip(),
            "related_name": clean_father,
            "father_name": clean_father,
            "agricultural_group": agricultural_group.strip(),
            "village_name": village_name.strip(),
            "credit_limit_paise": credit_limit_paise,
            "account_id": account_id,
        }
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO party(
                    party_id, name, related_name, father_name, agricultural_group,
                    village_name, party_type, account_id, credit_limit_paise,
                    address, city, gstin, pan, phone, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    party_id,
                    clean_name,
                    payload["related_name"] or None,
                    payload["father_name"] or None,
                    payload["agricultural_group"] or None,
                    payload["village_name"] or None,
                    party_type,
                    account_id,
                    credit_limit_paise,
                    payload["address"],
                    payload["city"],
                    clean_gstin or None,
                    payload["pan"] or None,
                    payload["phone"] or None,
                    timestamp,
                    timestamp,
                ),
            )
            self._audit(connection, None, "party", party_id, "create", payload)
        return {"party_id": party_id, "name": clean_name, "party_type": party_type}

    def update_party(
        self,
        party_id: str,
        *,
        name: str | None = None,
        father_name: str | None = None,
        agricultural_group: str | None = None,
        village_name: str | None = None,
        credit_limit_paise: int | None = None,
        gstin: str | None = None,
        pan: str | None = None,
        address: str | None = None,
        city: str | None = None,
        phone: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, str]:
        """Update an existing party master."""
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            current = connection.execute(
                "SELECT * FROM party WHERE party_id = ? AND is_deleted = 0",
                (party_id,),
            ).fetchone()
            if current is None:
                raise ValidationError("Party does not exist")
            updates: dict[str, object] = {}
            if name is not None:
                updates["name"] = self._required_text(name, "Party name")
            if father_name is not None:
                clean_father = father_name.strip()
                updates["father_name"] = clean_father or None
                updates["related_name"] = clean_father or None
            if agricultural_group is not None:
                updates["agricultural_group"] = agricultural_group.strip() or None
            if village_name is not None:
                updates["village_name"] = village_name.strip() or None
            if credit_limit_paise is not None:
                if credit_limit_paise < 0:
                    raise ValidationError("Credit limit cannot be negative")
                updates["credit_limit_paise"] = credit_limit_paise
            if gstin is not None:
                clean_gstin = gstin.strip().upper()
                if clean_gstin and len(clean_gstin) != 15:
                    raise ValidationError("GSTIN must contain 15 characters")
                updates["gstin"] = clean_gstin or None
            if pan is not None:
                updates["pan"] = pan.strip().upper() or None
            if address is not None:
                updates["address"] = address.strip()
            if city is not None:
                updates["city"] = city.strip()
            if phone is not None:
                updates["phone"] = phone.strip()
            if account_id is not None:
                updates["account_id"] = account_id
            if not updates:
                raise ValidationError("No party fields were provided to update")
            assignments = ", ".join(f"{column} = ?" for column in updates)
            connection.execute(
                f"""
                UPDATE party
                SET {assignments}, version = version + 1, updated_at = ?
                WHERE party_id = ?
                """,
                (*updates.values(), timestamp, party_id),
            )
            self._audit(
                connection,
                None,
                "party",
                party_id,
                "update",
                {"party_id": party_id, **updates},
            )
        return {"party_id": party_id, "name": str(updates.get("name", current["name"]))}

    def list_agricultural_groups(self) -> list[str]:
        """Return distinct agricultural groups configured on party masters."""
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT agricultural_group FROM party
                WHERE is_deleted = 0
                    AND agricultural_group IS NOT NULL
                    AND trim(agricultural_group) != ''
                ORDER BY agricultural_group COLLATE NOCASE
                """
            ).fetchall()
        return [str(row["agricultural_group"]) for row in rows]

    def create_commodity(
        self,
        name: str,
        *,
        variety: str = "",
        hsn_code: str = "",
        quantity_scale: int = 3,
        standard_bag_weight_scaled: int | None = None,
    ) -> dict[str, object]:
        """Create a commodity/variety master."""
        clean_name = self._required_text(name, "Commodity name")
        if quantity_scale < 0 or quantity_scale > 6:
            raise ValidationError("Quantity scale must be between 0 and 6")
        commodity_id = str(uuid.uuid4())
        timestamp = utc_now()
        payload: dict[str, object] = {
            "commodity_id": commodity_id,
            "name": clean_name,
            "variety": variety.strip(),
            "hsn_code": hsn_code.strip(),
            "quantity_scale": quantity_scale,
            "standard_bag_weight_scaled": standard_bag_weight_scaled,
        }
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO commodity(
                    commodity_id, name, variety, hsn_code, quantity_scale,
                    standard_bag_weight_scaled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commodity_id,
                    clean_name,
                    payload["variety"],
                    payload["hsn_code"] or None,
                    quantity_scale,
                    standard_bag_weight_scaled,
                    timestamp,
                    timestamp,
                ),
            )
            self._audit(connection, None, "commodity", commodity_id, "create", payload)
        return payload

    def create_charge_rule(
        self,
        *,
        code: str,
        label: str,
        transaction_type: str,
        basis: str,
        mode: str,
        rate_decimal: str,
        effective_from: str,
        effective_to: str | None = None,
        direction: str = "add",
        is_tax: bool = False,
        commodity_id: str | None = None,
        party_id: str | None = None,
        ledger_account_id: str | None = None,
        priority: int = 100,
    ) -> dict[str, object]:
        """Create an effective-dated calculation rule."""
        if basis not in {"amount", "bag", "quantity", "weight"}:
            raise ValidationError("Invalid charge basis")
        if mode not in {"percentage", "fixed"}:
            raise ValidationError("Invalid charge mode")
        if direction not in {"add", "deduct"}:
            raise ValidationError("Invalid charge direction")
        try:
            rate = Decimal(rate_decimal)
            starts_on = date.fromisoformat(effective_from)
            ends_on = date.fromisoformat(effective_to) if effective_to else None
        except (ValueError, ArithmeticError) as exc:
            raise ValidationError("Invalid rate or effective date") from exc
        if rate < 0:
            raise ValidationError("Charge rate cannot be negative")
        if ends_on and ends_on < starts_on:
            raise ValidationError("Effective end date cannot precede start date")
        rule_id = str(uuid.uuid4())
        timestamp = utc_now()
        payload: dict[str, object] = {
            "charge_rule_id": rule_id,
            "code": self._required_text(code, "Charge code").upper(),
            "label": self._required_text(label, "Charge label"),
            "transaction_type": self._required_text(
                transaction_type, "Transaction type"
            ),
            "basis": basis,
            "mode": mode,
            "rate_decimal": str(rate),
            "direction": direction,
            "is_tax": is_tax,
            "effective_from": starts_on.isoformat(),
            "effective_to": ends_on.isoformat() if ends_on else None,
            "commodity_id": commodity_id,
            "party_id": party_id,
            "ledger_account_id": ledger_account_id,
            "priority": priority,
        }
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO charge_rule(
                    charge_rule_id, code, label, transaction_type, commodity_id,
                    party_id, basis, mode, rate_decimal, direction, is_tax,
                    ledger_account_id, priority, effective_from, effective_to,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule_id,
                    payload["code"],
                    payload["label"],
                    payload["transaction_type"],
                    commodity_id,
                    party_id,
                    basis,
                    mode,
                    payload["rate_decimal"],
                    direction,
                    int(is_tax),
                    ledger_account_id,
                    priority,
                    payload["effective_from"],
                    payload["effective_to"],
                    timestamp,
                    timestamp,
                ),
            )
            self._audit(connection, None, "charge_rule", rule_id, "create", payload)
        return payload

    def list_charge_rules(
        self,
        *,
        transaction_type: str | None = None,
        as_of_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return effective charge rules for administration screens."""
        effective = as_of_date or date.today().isoformat()
        with self.databases.connect(self.database_path) as connection:
            if transaction_type:
                rows = connection.execute(
                    """
                    SELECT * FROM charge_rule
                    WHERE is_deleted = 0
                        AND transaction_type = ?
                        AND effective_from <= ?
                        AND (effective_to IS NULL OR effective_to >= ?)
                    ORDER BY transaction_type, priority, code, effective_from DESC
                    """,
                    (transaction_type, effective, effective),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM charge_rule
                    WHERE is_deleted = 0
                        AND effective_from <= ?
                        AND (effective_to IS NULL OR effective_to >= ?)
                    ORDER BY transaction_type, priority, code, effective_from DESC
                    """,
                    (effective, effective),
                ).fetchall()
        return [dict(row) for row in rows]

    def revise_charge_rule(
        self,
        charge_rule_id: str,
        *,
        rate_decimal: str | None = None,
        label: str | None = None,
        effective_from: str | None = None,
        effective_to: str | None = None,
        priority: int | None = None,
    ) -> dict[str, object]:
        """End-date the current rule and insert a successor without rewriting history."""
        with self.databases.connect(self.database_path) as connection:
            current = connection.execute(
                """
                SELECT * FROM charge_rule
                WHERE charge_rule_id = ? AND is_deleted = 0
                """,
                (charge_rule_id,),
            ).fetchone()
            if current is None:
                raise ValidationError("Charge rule does not exist")
            timestamp = utc_now()
            new_starts = effective_from or date.today().isoformat()
            try:
                starts_on = date.fromisoformat(new_starts)
                ends_previous = (starts_on.fromordinal(starts_on.toordinal() - 1)).isoformat()
            except ValueError as exc:
                raise ValidationError("Effective date is invalid") from exc
            connection.execute(
                """
                UPDATE charge_rule
                SET effective_to = ?, version = version + 1, updated_at = ?
                WHERE charge_rule_id = ?
                    AND (effective_to IS NULL OR effective_to >= ?)
                """,
                (ends_previous, timestamp, charge_rule_id, new_starts),
            )
            successor_id = str(uuid.uuid4())
            payload: dict[str, object] = {
                "charge_rule_id": successor_id,
                "code": current["code"],
                "label": label or current["label"],
                "transaction_type": current["transaction_type"],
                "basis": current["basis"],
                "mode": current["mode"],
                "rate_decimal": rate_decimal or current["rate_decimal"],
                "direction": current["direction"],
                "is_tax": bool(current["is_tax"]),
                "commodity_id": current["commodity_id"],
                "party_id": current["party_id"],
                "ledger_account_id": current["ledger_account_id"],
                "priority": priority if priority is not None else int(current["priority"]),
                "effective_from": new_starts,
                "effective_to": effective_to,
            }
            if Decimal(str(payload["rate_decimal"])) < 0:
                raise ValidationError("Charge rate cannot be negative")
            connection.execute(
                """
                INSERT INTO charge_rule(
                    charge_rule_id, code, label, transaction_type, commodity_id,
                    party_id, basis, mode, rate_decimal, direction, is_tax,
                    ledger_account_id, priority, effective_from, effective_to,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    successor_id,
                    payload["code"],
                    payload["label"],
                    payload["transaction_type"],
                    payload["commodity_id"],
                    payload["party_id"],
                    payload["basis"],
                    payload["mode"],
                    payload["rate_decimal"],
                    payload["direction"],
                    int(bool(payload["is_tax"])),
                    payload["ledger_account_id"],
                    payload["priority"],
                    payload["effective_from"],
                    payload["effective_to"],
                    timestamp,
                    timestamp,
                ),
            )
            self._audit(
                connection,
                None,
                "charge_rule",
                successor_id,
                "revise",
                {"previous_rule_id": charge_rule_id, **payload},
            )
        return payload

    def search(self, entity_type: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search an allowed master using prefix then token matching."""
        if entity_type not in SEARCH_TABLES:
            raise ValidationError("Unsupported lookup type")
        if limit < 1 or limit > 50:
            raise ValidationError("Lookup limit must be between 1 and 50")
        identifier, label, table = SEARCH_TABLES[entity_type]
        clean_query = " ".join(query.split())
        prefix = f"{clean_query}%"
        contains = f"%{clean_query}%"
        extra_columns = (
            """,
            address, gstin, phone, account_id, related_name, father_name,
            agricultural_group, village_name, credit_limit_paise,
            (SELECT name FROM account
             WHERE account.account_id = party.account_id) AS account_name
            """
            if entity_type == "party"
            else ""
        )
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT {identifier} AS id, {label} AS label{extra_columns}
                FROM {table}
                WHERE is_deleted = 0 AND {label} LIKE ? COLLATE NOCASE
                ORDER BY
                    CASE WHEN {label} LIKE ? COLLATE NOCASE THEN 0 ELSE 1 END,
                    {label} COLLATE NOCASE
                LIMIT ?
                """,
                (contains, prefix, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def post_voucher(
        self,
        *,
        financial_year_id: str,
        voucher_type: str,
        voucher_number: str,
        voucher_date: str,
        narration: str,
        lines: list[dict[str, Any]],
        credit_override_confirmed: bool = False,
        manager_override_pin: str = "",
    ) -> dict[str, object]:
        """Validate and atomically post a balanced voucher."""
        from .credit import CreditLimitService
        from .errors import CreditLimitBreachedError

        parsed_date = date.fromisoformat(voucher_date)
        settings_row: dict[str, Any] = {}
        with self.databases.connect(self.database_path) as settings_connection:
            row = settings_connection.execute(
                "SELECT settings_json FROM company_settings WHERE settings_key = 'default'"
            ).fetchone()
            settings_row = merge_company_settings(
                {} if row is None else json.loads(str(row["settings_json"] or "{}"))
            )
        evaluate_backdate_policy(
            role=current_access().role,
            voucher_date=parsed_date,
            today=date.today(),
            settings=settings_row,
        )
        ledger_lines = [
            LedgerLine(
                account_id=str(line["account_id"]),
                debit_paise=int(line.get("debit_paise", 0)),
                credit_paise=int(line.get("credit_paise", 0)),
            )
            for line in lines
        ]
        validate_balanced(ledger_lines)
        voucher_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            year = self._require_open_year(connection, financial_year_id)
            if not FinancialYear(int(year["start_year"])).contains(parsed_date):
                raise ValidationError("Voucher date is outside the selected financial year")
            account_ids = {line.account_id for line in ledger_lines}
            placeholders = ",".join("?" for _ in account_ids)
            existing = connection.execute(
                f"""
                SELECT account_id FROM account
                WHERE account_id IN ({placeholders}) AND is_deleted = 0
                """,
                tuple(account_ids),
            ).fetchall()
            if len(existing) != len(account_ids):
                raise ValidationError("Voucher contains an invalid account")
            credit_service = CreditLimitService(self.databases, self.company_id)
            for line in ledger_lines:
                if line.debit_paise <= 0:
                    continue
                party = connection.execute(
                    """
                    SELECT party_id FROM party
                    WHERE account_id = ? AND is_deleted = 0
                    LIMIT 1
                    """,
                    (line.account_id,),
                ).fetchone()
                if party is None:
                    continue
                evaluation = credit_service.evaluate_credit(
                    party_id=str(party["party_id"]),
                    financial_year_id=financial_year_id,
                    additional_debit_paise=line.debit_paise,
                    connection=connection,
                )
                if evaluation["breached"] and not credit_override_confirmed:
                    raise CreditLimitBreachedError(
                        "Credit limit breached for "
                        f"{evaluation['party_name']}: overage "
                        f"{evaluation['overage_paise']} paise"
                    )
                if evaluation["breached"] and credit_override_confirmed:
                    if not verify_manager_pin(settings_row, manager_override_pin):
                        raise ValidationError(
                            "Manager/Admin PIN is required to override credit limit"
                        )
            connection.execute(
                """
                INSERT INTO voucher(
                    voucher_id, financial_year_id, voucher_type, voucher_number,
                    voucher_date, narration, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'posted', ?, ?)
                """,
                (
                    voucher_id,
                    financial_year_id,
                    self._required_text(voucher_type, "Voucher type"),
                    self._required_text(voucher_number, "Voucher number"),
                    voucher_date,
                    narration.strip(),
                    timestamp,
                    timestamp,
                ),
            )
            for index, line in enumerate(ledger_lines, start=1):
                connection.execute(
                    """
                    INSERT INTO voucher_line(
                        voucher_line_id, voucher_id, account_id, line_number,
                        debit_paise, credit_paise
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        voucher_id,
                        line.account_id,
                        index,
                        line.debit_paise,
                        line.credit_paise,
                    ),
                )
            payload = {
                "voucher_id": voucher_id,
                "financial_year_id": financial_year_id,
                "voucher_type": voucher_type,
                "voucher_number": voucher_number,
                "voucher_date": voucher_date,
                "narration": narration.strip(),
                "lines": lines,
            }
            self._audit(
                connection,
                financial_year_id,
                "voucher",
                voucher_id,
                "post",
                payload,
                reason="credit_override" if credit_override_confirmed else None,
            )
        return {
            "voucher_id": voucher_id,
            "debit_paise": sum(line.debit_paise for line in ledger_lines),
            "credit_paise": sum(line.credit_paise for line in ledger_lines),
            "status": "posted",
        }

    def trial_balance(self, financial_year_id: str) -> list[dict[str, Any]]:
        """Return account opening plus posted movement balances."""
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    a.account_id,
                    a.name,
                    a.account_type,
                    a.opening_debit_paise
                        + COALESCE(SUM(vl.debit_paise), 0) AS debit_paise,
                    a.opening_credit_paise
                        + COALESCE(SUM(vl.credit_paise), 0) AS credit_paise
                FROM account a
                LEFT JOIN voucher_line vl ON vl.account_id = a.account_id
                LEFT JOIN voucher v
                    ON v.voucher_id = vl.voucher_id
                    AND v.financial_year_id = ?
                    AND v.status IN ('posted', 'reversed')
                WHERE a.is_deleted = 0
                    AND (a.financial_year_id IS NULL OR a.financial_year_id = ?)
                GROUP BY a.account_id, a.name, a.account_type,
                    a.opening_debit_paise, a.opening_credit_paise
                ORDER BY a.name COLLATE NOCASE
                """,
                (financial_year_id, financial_year_id),
            ).fetchall()
        return [
            {
                **dict(row),
                "balance_paise": int(row["debit_paise"]) - int(row["credit_paise"]),
            }
            for row in rows
        ]

    def reverse_voucher(
        self,
        voucher_id: str,
        reversal_number: str,
        reversal_date: str,
        reason: str,
    ) -> dict[str, str]:
        """Reverse a posted manual voucher with equal opposite lines."""
        clean_reason = self._required_text(reason, "Reversal reason")
        timestamp = utc_now()
        reversal_id = str(uuid.uuid4())
        with self.databases.connect(self.database_path) as connection:
            voucher = connection.execute(
                """
                SELECT * FROM voucher
                WHERE voucher_id = ? AND status = 'posted'
                """,
                (voucher_id,),
            ).fetchone()
            if voucher is None:
                raise StateError("Only a posted voucher can be reversed")
            self._require_open_year(connection, str(voucher["financial_year_id"]))
            lines = connection.execute(
                """
                SELECT * FROM voucher_line
                WHERE voucher_id = ? ORDER BY line_number
                """,
                (voucher_id,),
            ).fetchall()
            connection.execute(
                """
                INSERT INTO voucher(
                    voucher_id, financial_year_id, voucher_type, voucher_number,
                    voucher_date, narration, status, reversal_of_voucher_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'posted', ?, ?, ?)
                """,
                (
                    reversal_id,
                    voucher["financial_year_id"],
                    f"{voucher['voucher_type']}_reversal",
                    self._required_text(reversal_number, "Reversal number"),
                    reversal_date,
                    clean_reason,
                    voucher_id,
                    timestamp,
                    timestamp,
                ),
            )
            for line in lines:
                connection.execute(
                    """
                    INSERT INTO voucher_line(
                        voucher_line_id, voucher_id, account_id, line_number,
                        debit_paise, credit_paise, narration
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        reversal_id,
                        line["account_id"],
                        line["line_number"],
                        line["credit_paise"],
                        line["debit_paise"],
                        clean_reason,
                    ),
                )
            connection.execute(
                """
                UPDATE voucher SET status = 'reversed', updated_at = ?
                WHERE voucher_id = ?
                """,
                (timestamp, voucher_id),
            )
            payload = {
                "voucher_id": reversal_id,
                "reversal_of_voucher_id": voucher_id,
                "reason": clean_reason,
            }
            self._audit(
                connection,
                str(voucher["financial_year_id"]),
                "voucher",
                voucher_id,
                "reverse",
                payload,
                reason=clean_reason,
            )
        return {"voucher_id": reversal_id, "reversal_of_voucher_id": voucher_id}

    @staticmethod
    def _required_text(value: str, label: str) -> str:
        """Normalize and validate required text."""
        clean = " ".join(value.split())
        if not clean:
            raise ValidationError(f"{label} is required")
        return clean

    @staticmethod
    def _require_open_year(connection: Any, financial_year_id: str) -> Any:
        """Load a financial year and reject locked periods."""
        row = connection.execute(
            """
            SELECT start_year, is_locked FROM financial_year
            WHERE financial_year_id = ?
            """,
            (financial_year_id,),
        ).fetchone()
        if row is None:
            raise ValidationError("Financial year does not exist")
        if row["is_locked"]:
            raise StateError("Financial year is locked")
        return row

    @staticmethod
    def _audit(
        connection: Any,
        financial_year_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        payload: dict[str, Any],
        *,
        reason: str | None = None,
    ) -> None:
        """Append an immutable local audit event."""
        connection.execute(
            """
            INSERT INTO audit_event(
                audit_event_id, financial_year_id, entity_type, entity_id,
                action, reason, payload_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                financial_year_id,
                entity_type,
                entity_id,
                action,
                reason,
                json.dumps(payload, sort_keys=True),
                utc_now(),
            ),
        )
