"""GSTR-1 style document serial summary (doc_issue)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from .database import DatabaseManager
from .database import utc_now
from .errors import ValidationError
from .gst_compliance import GST_DOC_NATURE_BY_TYPE

_SERIAL_RE = re.compile(r"^(?P<prefix>.*?)(?P<num>\d+)$")


def _split_serial(document_number: str) -> tuple[str, int]:
    clean = str(document_number or "").strip()
    match = _SERIAL_RE.match(clean)
    if not match:
        return clean, 0
    return str(match.group("prefix")), int(match.group("num"))


class GstDocumentIssueService:
    """Persist and query outward document serial ranges for GST returns."""

    def __init__(self, databases: DatabaseManager, database_path: str) -> None:
        self.databases = databases
        self.database_path = database_path

    def refresh(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, object]:
        if not financial_year_id:
            raise ValidationError("Financial year is required")
        rows = self._compute(financial_year_id, date_from, date_to)
        timestamp = utc_now()
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                DELETE FROM gst_doc_issue
                WHERE financial_year_id = ? AND period_from = ? AND period_to = ?
                """,
                (financial_year_id, date_from, date_to),
            )
            for row in rows:
                connection.execute(
                    """
                    INSERT INTO gst_doc_issue(
                        gst_doc_issue_id, financial_year_id, period_from, period_to,
                        gst_nature, number_prefix, serial_from, serial_to,
                        total_count, cancelled_count, refreshed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        financial_year_id,
                        date_from,
                        date_to,
                        row["gst_nature"],
                        row["number_prefix"],
                        row["serial_from"],
                        row["serial_to"],
                        row["total_count"],
                        row["cancelled_count"],
                        timestamp,
                    ),
                )
        return {"refreshed": len(rows), "rows": rows}

    def list_rows(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            cached = connection.execute(
                """
                SELECT gst_nature, number_prefix, serial_from, serial_to,
                    total_count, cancelled_count, refreshed_at
                FROM gst_doc_issue
                WHERE financial_year_id = ? AND period_from = ? AND period_to = ?
                ORDER BY gst_nature, number_prefix
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        if cached:
            return [dict(row) for row in cached]
        return self._compute(financial_year_id, date_from, date_to)

    def _compute(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            docs = connection.execute(
                """
                SELECT document_type, document_number, status
                FROM document
                WHERE financial_year_id = ?
                  AND document_date >= ? AND document_date <= ?
                  AND status IN ('posted', 'reversed')
                ORDER BY document_type, document_number
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        buckets: dict[tuple[str, str], list[dict[str, str]]] = {}
        for row in docs:
            doc_type = str(row["document_type"])
            nature = GST_DOC_NATURE_BY_TYPE.get(doc_type)
            if not nature:
                continue
            prefix, serial_num = _split_serial(str(row["document_number"]))
            key = (nature, prefix)
            buckets.setdefault(key, []).append(
                {
                    "document_number": str(row["document_number"]),
                    "status": str(row["status"]),
                    "serial_num": serial_num,
                    "prefix": prefix,
                }
            )
        output: list[dict[str, Any]] = []
        for (nature, prefix), items in sorted(buckets.items()):
            numeric = [int(item["serial_num"]) for item in items if item["serial_num"] > 0]
            cancelled = sum(1 for item in items if item["status"] == "reversed")
            if numeric:
                serial_from = f"{prefix}{min(numeric)}"
                serial_to = f"{prefix}{max(numeric)}"
            else:
                numbers = sorted(item["document_number"] for item in items)
                serial_from = numbers[0]
                serial_to = numbers[-1]
            output.append(
                {
                    "gst_nature": nature,
                    "number_prefix": prefix,
                    "serial_from": serial_from,
                    "serial_to": serial_to,
                    "total_count": len(items),
                    "cancelled_count": cancelled,
                    "net_issued": len(items) - cancelled,
                }
            )
        return output
