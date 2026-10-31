"""Bardana (empty bag) dual-quantity tracking — jute, plastic, HDPE."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .database import DatabaseManager
from .database import utc_now
from .errors import ValidationError
from .mandi_business import merge_company_settings


BARDANA_TYPES = frozenset({"jute", "plastic", "hdpe"})


class BardanaService:
    """Track inward bags with crop and outward loans/sales of empty bags."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.database_path = databases.company_path(company_id)

    def _require_enabled(self, connection: Any) -> None:
        row = connection.execute(
            "SELECT settings_json FROM company_settings WHERE settings_key = 'default'"
        ).fetchone()
        settings = merge_company_settings(
            {} if row is None else json.loads(str(row["settings_json"] or "{}"))
        )
        if not settings.get("features", {}).get("bardana_tracking", True):
            raise ValidationError("Bardana tracking is disabled in company settings")

    def record_movement(
        self,
        *,
        financial_year_id: str,
        movement_type: str,
        bardana_type: str,
        bags: int,
        party_id: str | None = None,
        document_id: str | None = None,
        remarks: str = "",
    ) -> dict[str, str]:
        """Record inward (+) or outward (-) bardana movement."""
        clean_type = bardana_type.strip().lower()
        if clean_type not in BARDANA_TYPES:
            raise ValidationError("Bardana type must be jute, plastic, or hdpe")
        if movement_type not in {"inward", "outward", "adjustment"}:
            raise ValidationError("Movement type must be inward, outward, or adjustment")
        if bags == 0:
            raise ValidationError("Bag quantity cannot be zero")
        signed = abs(bags) if movement_type == "inward" else -abs(bags)
        movement_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            self._require_enabled(connection)
            connection.execute(
                """
                INSERT INTO bardana_movement(
                    movement_id, financial_year_id, movement_type, bardana_type,
                    bags_signed, party_id, document_id, remarks, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    movement_id,
                    financial_year_id,
                    movement_type,
                    clean_type,
                    signed,
                    party_id,
                    document_id,
                    remarks.strip(),
                    timestamp,
                ),
            )
        return {"movement_id": movement_id}

    def stock_summary(self, financial_year_id: str) -> list[dict[str, Any]]:
        """Book stock by bardana material type."""
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT bardana_type, SUM(bags_signed) AS book_bags
                FROM bardana_movement
                WHERE financial_year_id = ?
                GROUP BY bardana_type
                ORDER BY bardana_type
                """,
                (financial_year_id,),
            ).fetchall()
        return [
            {"bardana_type": str(r["bardana_type"]), "book_bags": int(r["book_bags"])}
            for r in rows
        ]
