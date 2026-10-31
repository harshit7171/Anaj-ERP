"""GST report menu — item/group lookups."""

from __future__ import annotations

from typing import Any

from .database import DatabaseManager


class GstReportsService:
    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)

    def lookup_items(self, query: str = "", limit: int = 50) -> list[dict[str, Any]]:
        clean = str(query or "").strip()
        pattern = f"%{clean}%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT commodity_id, name AS item_name, variety AS item_group, hsn_code
                FROM commodity
                WHERE is_deleted = 0
                  AND (name LIKE ? COLLATE NOCASE OR variety LIKE ? COLLATE NOCASE)
                ORDER BY name COLLATE NOCASE
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def lookup_item_groups(self, query: str = "", limit: int = 50) -> list[dict[str, Any]]:
        clean = str(query or "").strip()
        pattern = f"%{clean}%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT COALESCE(NULLIF(trim(variety), ''), name) AS group_name
                FROM commodity
                WHERE is_deleted = 0
                  AND (variety LIKE ? COLLATE NOCASE OR name LIKE ? COLLATE NOCASE)
                ORDER BY group_name COLLATE NOCASE
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()
        return [{"group_name": str(row["group_name"])} for row in rows if row["group_name"]]
