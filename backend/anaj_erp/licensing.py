"""Signed annual offline license installation and validation."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import date
from datetime import timedelta
from typing import Any

DEMO_DAYS = 15

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .database import DatabaseManager
from .database import utc_now
from .errors import ClockTamperException
from .errors import LicenseWriteLockedError
from .errors import StateError
from .errors import ValidationError
from .security import protect_for_current_user
from .security import unprotect_for_current_user


def _decode(value: str) -> bytes:
    """Decode URL-safe base64 without requiring caller padding."""
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class LicenseService:
    """Verify vendor-signed entitlements without network access."""

    def __init__(self, databases: DatabaseManager, public_key_pem: bytes) -> None:
        """Load the vendor public key and bind to installation storage."""
        key = serialization.load_pem_public_key(public_key_pem)
        if not isinstance(key, Ed25519PublicKey):
            raise ValidationError("License public key must be Ed25519")
        self.public_key = key
        self.databases = databases

    def install(self, token: str, today: date | None = None) -> dict[str, Any]:
        """Verify and install a license entered during AnyDesk support."""
        payload, payload_text, signature_text = self._verify_token(token)
        current_date = today or date.today()
        if payload.get("installation_id") != self.databases.installation_id():
            raise ValidationError("License was issued for another installation")
        try:
            valid_from = date.fromisoformat(str(payload["valid_from"]))
            valid_until = date.fromisoformat(str(payload["valid_until"]))
        except (KeyError, ValueError) as exc:
            raise ValidationError("License validity dates are invalid") from exc
        if valid_until < valid_from:
            raise ValidationError("License end date precedes start date")
        if (valid_until.month, valid_until.day) != (4, 30):
            raise ValidationError("Annual license must end on April 30")
        license_id = str(payload.get("license_id") or uuid.uuid4())
        protected = self._protect_state(license_id, current_date)
        with self.databases.connect(self.databases.catalog_path) as connection:
            connection.execute("UPDATE license_state SET is_revoked = 1")
            connection.execute(
                """
                INSERT INTO license_state(
                    license_id, installation_id, customer_name, valid_from,
                    valid_until, signed_payload, signature, installed_at,
                    last_seen_date, protected_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    license_id,
                    payload["installation_id"],
                    str(payload.get("customer_name", "")).strip() or "Licensed Customer",
                    valid_from.isoformat(),
                    valid_until.isoformat(),
                    payload_text,
                    signature_text,
                    utc_now(),
                    current_date.isoformat(),
                    protected,
                ),
            )
        return self.status(today=current_date)

    def status(self, today: date | None = None) -> dict[str, Any]:
        """Validate the active license, phase and protected clock progression."""
        current_date = today or date.today()
        with self.databases.connect(self.databases.catalog_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM license_state
                WHERE is_revoked = 0
                ORDER BY installed_at DESC LIMIT 1
                """
            ).fetchone()
            if row is None:
                demo = self._demo_status(connection, current_date)
                if demo is not None:
                    return demo
                return {
                    "valid": False,
                    "writable": False,
                    "phase": "unlicensed",
                    "reason": "No annual license is installed",
                }
            token = f"{row['signed_payload']}.{row['signature']}"
            payload, _, _ = self._verify_token(token)
            protected_state = self._unprotect_state(bytes(row["protected_state"]))
            if protected_state["license_id"] != row["license_id"]:
                raise StateError("Protected license state does not match the license")
            protected_last_seen = date.fromisoformat(protected_state["last_seen_date"])
            database_last_seen = date.fromisoformat(str(row["last_seen_date"]))
            last_seen = max(protected_last_seen, database_last_seen)
            if current_date < last_seen:
                return {
                    "valid": False,
                    "writable": False,
                    "phase": "clock_tamper",
                    "reason": "System date is earlier than the last licensed use",
                    "clock_rollback": True,
                    "last_seen_date": last_seen.isoformat(),
                }
            valid_from = date.fromisoformat(str(row["valid_from"]))
            valid_until = date.fromisoformat(str(row["valid_until"]))
            valid = valid_from <= current_date <= valid_until
            warning_start = date(valid_until.year, 4, 11)
            if current_date > valid_until:
                phase = "expired"
                reason = "Subscription Expired. Please contact support to renew your license key."
                warning_message = ""
            elif valid and current_date >= warning_start:
                phase = "warning"
                reason = ""
                warning_message = (
                    f"Your subscription expires on 30-Apr-{valid_until.year}. "
                    "Please renew to avoid service disruption."
                )
            elif valid:
                phase = "active"
                reason = ""
                warning_message = ""
            else:
                phase = "not_started"
                reason = "Annual license is outside its validity period"
                warning_message = ""
            if current_date > last_seen:
                protected = self._protect_state(str(row["license_id"]), current_date)
                connection.execute(
                    """
                    UPDATE license_state
                    SET last_seen_date = ?, protected_state = ?
                    WHERE license_id = ?
                    """,
                    (current_date.isoformat(), protected, row["license_id"]),
                )
        features = payload.get("features") or payload.get("Features") or []
        if isinstance(features, str):
            features = [features]
        return {
            "valid": valid,
            "writable": phase in {"active", "warning"},
            "phase": phase,
            "reason": reason,
            "warning_message": warning_message,
            "license_id": row["license_id"],
            "customer_name": row["customer_name"],
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
            "payload": payload,
            "features": list(features),
        }

    def assert_session_safe(self, today: date | None = None) -> dict[str, Any]:
        """Reject all business sessions immediately after detected clock rollback."""
        status = self.status(today=today)
        if status.get("phase") == "clock_tamper":
            raise ClockTamperException(
                "System clock rollback detected. Correct the Windows date and contact support."
            )
        return status

    def assert_can_open(self, today: date | None = None) -> dict[str, Any]:
        """Allow historical read-only access but reject missing/future licenses."""
        status = self.assert_session_safe(today=today)
        if status.get("phase") in {"unlicensed", "not_started", "demo_expired"}:
            raise LicenseWriteLockedError(str(status.get("reason", "License is not active")))
        return status

    def assert_can_write(self, today: date | None = None) -> dict[str, Any]:
        """Reject every data modification outside the active or warning phase."""
        status = self.assert_session_safe(today=today)
        if status.get("phase") == "demo_expired":
            raise LicenseWriteLockedError(str(status.get("reason")))
        if not status.get("writable"):
            raise LicenseWriteLockedError(
                "Subscription Expired. Please contact support to renew your license key."
            )
        return status

    def _demo_status(self, connection: Any, current_date: date) -> dict[str, Any] | None:
        """15-day full-feature demo for first-time installations without a license."""
        row = connection.execute(
            "SELECT demo_started_at FROM installation LIMIT 1"
        ).fetchone()
        if row is None or not row["demo_started_at"]:
            return None
        try:
            started = date.fromisoformat(str(row["demo_started_at"]))
        except ValueError:
            return None
        ends = started + timedelta(days=DEMO_DAYS - 1)
        if current_date <= ends:
            remaining = (ends - current_date).days + 1
            return {
                "valid": True,
                "writable": True,
                "phase": "demo",
                "reason": "",
                "warning_message": (
                    f"Demo mode: {remaining} day(s) left. Enter a license key before "
                    f"{ends.isoformat()} to continue posting vouchers."
                ),
                "demo_ends": ends.isoformat(),
                "features": ["GRAIN", "MULTI_USER", "DEMO"],
            }
        return {
            "valid": False,
            "writable": False,
            "phase": "demo_expired",
            "reason": (
                "15-day demo expired. Enter your subscription license key under "
                "Tools → Software Registration & Validation."
            ),
            "warning_message": "",
            "demo_ended": ends.isoformat(),
        }

    def _verify_token(self, token: str) -> tuple[dict[str, Any], str, str]:
        """Verify signature and parse a two-part license token."""
        try:
            payload_text, signature_text = token.strip().split(".", maxsplit=1)
            payload_bytes = _decode(payload_text)
            signature = _decode(signature_text)
            self.public_key.verify(signature, payload_bytes)
            payload = json.loads(payload_bytes)
        except (ValueError, json.JSONDecodeError, InvalidSignature) as exc:
            raise ValidationError("License key is invalid or has been altered") from exc
        if not isinstance(payload, dict):
            raise ValidationError("License payload must be an object")
        return payload, payload_text, signature_text

    @staticmethod
    def _protect_state(license_id: str, last_seen: date) -> bytes:
        """Protect anti-rollback state with Windows DPAPI."""
        payload = json.dumps(
            {"license_id": license_id, "last_seen_date": last_seen.isoformat()},
            sort_keys=True,
        ).encode("utf-8")
        return protect_for_current_user(payload)

    @staticmethod
    def _unprotect_state(value: bytes) -> dict[str, str]:
        """Unprotect and parse anti-rollback state."""
        try:
            state = json.loads(unprotect_for_current_user(value))
        except (ValueError, json.JSONDecodeError) as exc:
            raise StateError("Protected license state is damaged") from exc
        if not isinstance(state, dict):
            raise StateError("Protected license state is invalid")
        return {str(key): str(item) for key, item in state.items()}
