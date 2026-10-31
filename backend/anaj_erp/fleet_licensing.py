"""Vendor-side fleet licensing registry (renewals and revocations)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .database import utc_now
from .errors import ValidationError

FLEET_SCHEMA = """
CREATE TABLE IF NOT EXISTS fleet_machine (
    machine_id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    last_seen_at TEXT,
    license_valid_until TEXT,
    is_revoked INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fleet_event (
    event_id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _encode_segment(value: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


class FleetRegistry:
    """SQLite-backed machine list for internal renewal desk."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.executescript(FLEET_SCHEMA)

    def heartbeat(
        self,
        installation_id: str,
        customer_name: str,
        *,
        license_valid_until: str = "",
        app_version: str = "",
    ) -> dict[str, Any]:
        clean_id = installation_id.strip()
        if not clean_id:
            raise ValidationError("installation_id required")
        now = utc_now()
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM fleet_machine WHERE installation_id = ?",
                (clean_id,),
            ).fetchone()
            if row and int(row["is_revoked"]):
                return {"ok": False, "revoked": True, "error": "Installation revoked"}
            machine_id = str(row["machine_id"]) if row else str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO fleet_machine(
                    machine_id, installation_id, customer_name, last_seen_at,
                    license_valid_until, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(installation_id) DO UPDATE SET
                    customer_name = excluded.customer_name,
                    last_seen_at = excluded.last_seen_at,
                    license_valid_until = COALESCE(NULLIF(excluded.license_valid_until, ''), fleet_machine.license_valid_until),
                    updated_at = excluded.updated_at
                """,
                (
                    machine_id,
                    clean_id,
                    customer_name.strip() or "Unknown",
                    now,
                    license_valid_until,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO fleet_event(event_id, installation_id, event_type, payload_json, created_at)
                VALUES (?, ?, 'heartbeat', ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    clean_id,
                    json.dumps({"app_version": app_version}),
                    now,
                ),
            )
        return {"ok": True, "machine_id": machine_id, "revoked": False}

    def list_machines(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT installation_id, customer_name, last_seen_at,
                    license_valid_until, is_revoked, notes
                FROM fleet_machine
                ORDER BY customer_name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def revoke(self, installation_id: str, *, revoked: bool = True) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE fleet_machine
                SET is_revoked = ?, updated_at = ?
                WHERE installation_id = ?
                """,
                (1 if revoked else 0, utc_now(), installation_id.strip()),
            )
        return {"ok": True, "installation_id": installation_id, "revoked": revoked}

    def issue_license_token(
        self,
        private_key_pem: bytes,
        *,
        installation_id: str,
        customer_name: str,
        valid_from: str,
        valid_until: str,
        features: list[str] | None = None,
    ) -> str:
        """Sign a renewal key (vendor private key — never ship to clients)."""
        key = serialization.load_pem_private_key(private_key_pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValidationError("Fleet issuer requires Ed25519 private key PEM")
        try:
            start = date.fromisoformat(valid_from)
            end = date.fromisoformat(valid_until)
        except ValueError as exc:
            raise ValidationError("valid_from / valid_until must be ISO dates") from exc
        if end < start:
            raise ValidationError("valid_until precedes valid_from")
        payload = {
            "license_id": str(uuid.uuid4()),
            "installation_id": installation_id.strip(),
            "customer_name": customer_name.strip() or "Licensed Customer",
            "Client": customer_name.strip() or "Licensed Customer",
            "valid_from": start.isoformat(),
            "valid_until": end.isoformat(),
            "Expiry": end.isoformat(),
            "features": features or ["GRAIN", "MULTI_USER"],
            "Features": features or ["GRAIN", "MULTI_USER"],
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = key.sign(payload_bytes)
        token = f"{_encode_segment(payload_bytes)}.{_encode_segment(signature)}"
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE fleet_machine
                SET license_valid_until = ?, updated_at = ?, customer_name = ?
                WHERE installation_id = ?
                """,
                (end.isoformat(), utc_now(), payload["customer_name"], installation_id.strip()),
            )
            connection.execute(
                """
                INSERT INTO fleet_event(event_id, installation_id, event_type, payload_json, created_at)
                VALUES (?, ?, 'issue_license', ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    installation_id.strip(),
                    json.dumps({"valid_until": end.isoformat()}),
                    utc_now(),
                ),
            )
        return token
