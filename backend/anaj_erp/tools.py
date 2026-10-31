"""Search, stock adjustment, and company tool settings."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .database import DatabaseManager
from .database import utc_now
from .mandi_business import hash_manager_pin
from .mandi_business import merge_company_settings
from .errors import ValidationError


class ToolsService:
    """Phase 5 tools operating on the active company database."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)

    def find_accounts(
        self,
        *,
        query: str = "",
        city: str = "",
        party_type: str = "",
    ) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            sql = """
                SELECT
                    p.party_id, p.name, p.party_type, p.city, p.phone, p.gstin,
                    a.account_id, a.name AS account_name,
                    a.opening_debit_paise, a.opening_credit_paise
                FROM party p
                LEFT JOIN account a ON a.account_id = p.account_id
                WHERE p.is_deleted = 0
            """
            params: list[Any] = []
            if query.strip():
                sql += " AND (p.name LIKE ? OR p.phone LIKE ? OR p.gstin LIKE ?)"
                pattern = f"%{query.strip()}%"
                params.extend([pattern, pattern, pattern])
            if city.strip():
                sql += " AND p.city LIKE ?"
                params.append(f"%{city.strip()}%")
            if party_type.strip():
                sql += " AND p.party_type = ?"
                params.append(party_type.strip())
            sql += " ORDER BY p.name COLLATE NOCASE LIMIT 500"
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def save_stock_adjustment(
        self,
        financial_year_id: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        commodity_id = str(payload.get("commodity_id", "")).strip()
        if not commodity_id:
            raise ValidationError("Commodity is required")
        adjustment_type = str(payload.get("adjustment_type", "increase")).strip().lower()
        if adjustment_type not in {"increase", "decrease", "wastage"}:
            raise ValidationError("Invalid adjustment type")
        sign = 1 if adjustment_type == "increase" else -1
        bags = int(payload.get("bags", 0))
        quantity_scaled = int(payload.get("quantity_scaled", 0))
        adjustment_id = str(payload.get("adjustment_id") or uuid.uuid4())
        timestamp = utc_now()
        movement_id = str(uuid.uuid4())
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO stock_adjustment(
                    adjustment_id, financial_year_id, adjustment_date, ref_no,
                    commodity_id, adjustment_type, bags, quantity_scaled,
                    rate_paise, amount_paise, remarks, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(adjustment_id) DO UPDATE SET
                    adjustment_date = excluded.adjustment_date,
                    ref_no = excluded.ref_no,
                    commodity_id = excluded.commodity_id,
                    adjustment_type = excluded.adjustment_type,
                    bags = excluded.bags,
                    quantity_scaled = excluded.quantity_scaled,
                    rate_paise = excluded.rate_paise,
                    amount_paise = excluded.amount_paise,
                    remarks = excluded.remarks,
                    updated_at = excluded.updated_at
                """,
                (
                    adjustment_id,
                    financial_year_id,
                    str(payload.get("adjustment_date", timestamp[:10])),
                    str(payload.get("ref_no", "")).strip() or None,
                    commodity_id,
                    adjustment_type,
                    bags,
                    quantity_scaled,
                    int(payload.get("rate_paise", 0)),
                    int(payload.get("amount_paise", 0)),
                    str(payload.get("remarks", "")).strip() or None,
                    timestamp,
                    timestamp,
                ),
            )
            occurred_on = str(payload.get("adjustment_date", timestamp[:10]))
            connection.execute(
                """
                INSERT INTO inventory_movement(
                    inventory_movement_id, financial_year_id, document_id,
                    commodity_id, warehouse_code, movement_type, quantity_scaled,
                    quantity_scale, bags_scaled, idempotency_key, occurred_on, created_at
                ) VALUES (?, ?, NULL, ?, 'MAIN', 'stock_adjustment', ?, 3, ?, ?, ?, ?)
                """,
                (
                    movement_id,
                    financial_year_id,
                    commodity_id,
                    sign * abs(quantity_scaled),
                    sign * abs(bags),
                    f"stock-adjustment:{adjustment_id}",
                    occurred_on,
                    timestamp,
                ),
            )
        return {"adjustment_id": adjustment_id, "movement_id": movement_id}

    def get_company_settings(self) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT settings_json FROM company_settings WHERE settings_key = 'default'"
            ).fetchone()
        if row is None:
            return merge_company_settings({})
        return merge_company_settings(json.loads(str(row["settings_json"] or "{}")))

    def save_company_settings(self, settings: dict[str, Any]) -> dict[str, object]:
        timestamp = utc_now()
        payload = dict(settings)
        plain_pin = str(payload.pop("manager_override_pin", "") or "").strip()
        if plain_pin:
            payload["manager_override_pin_hash"] = hash_manager_pin(plain_pin)
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO company_settings(settings_key, settings_json, updated_at)
                VALUES ('default', ?, ?)
                ON CONFLICT(settings_key) DO UPDATE SET
                    settings_json = excluded.settings_json,
                    updated_at = excluded.updated_at
                """,
                (json.dumps(payload, sort_keys=True), timestamp),
            )
        return {"saved": True}

    def list_prefix_settings(self, financial_year_id: str) -> list[dict[str, object]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT document_type, prefix, next_number
                FROM numbering_series
                WHERE financial_year_id = ?
                ORDER BY document_type
                """,
                (financial_year_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_prefix_setting(
        self,
        financial_year_id: str,
        document_type: str,
        prefix: str,
        next_number: int,
    ) -> dict[str, object]:
        if not document_type.strip() or not prefix.strip():
            raise ValidationError("Document type and prefix are required")
        if next_number < 1:
            raise ValidationError("Next number must be positive")
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO numbering_series(financial_year_id, document_type, prefix, next_number)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(financial_year_id, document_type) DO UPDATE SET
                    prefix = excluded.prefix,
                    next_number = excluded.next_number
                """,
                (financial_year_id, document_type.strip(), prefix.strip(), int(next_number)),
            )
        return {"document_type": document_type, "prefix": prefix, "next_number": next_number}

    def merge_parties(self, source_party_id: str, target_party_id: str) -> dict[str, object]:
        """Reassign documents and balances from one party to another (admin tool)."""
        source = source_party_id.strip()
        target = target_party_id.strip()
        if not source or not target or source == target:
            raise ValidationError("Select two different parties")
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT party_id, account_id, is_deleted
                FROM party
                WHERE party_id IN (?, ?)
                """,
                (source, target),
            ).fetchall()
            if len(rows) != 2 or any(int(row["is_deleted"]) for row in rows):
                raise ValidationError("Both parties must exist and be active")
            source_account = str(next(r["account_id"] for r in rows if r["party_id"] == source))
            target_account = str(next(r["account_id"] for r in rows if r["party_id"] == target))
            connection.execute(
                "UPDATE document SET party_id = ? WHERE party_id = ?",
                (target, source),
            )
            connection.execute(
                "UPDATE document SET ship_to_party_id = ? WHERE ship_to_party_id = ?",
                (target, source),
            )
            if source_account and target_account and source_account != target_account:
                connection.execute(
                    """
                    UPDATE voucher_line SET account_id = ?
                    WHERE account_id = ?
                    """,
                    (target_account, source_account),
                )
            connection.execute(
                """
                UPDATE party SET is_deleted = 1, updated_at = ?
                WHERE party_id = ?
                """,
                (timestamp, source),
            )
        return {"merged": True, "source_party_id": source, "target_party_id": target}
