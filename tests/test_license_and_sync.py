"""Security tests for offline licensing."""

import base64
import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from anaj_erp.api import ApplicationApi
from anaj_erp.database import DatabaseManager
from anaj_erp.errors import ClockTamperException
from anaj_erp.errors import LicenseWriteLockedError
from anaj_erp.licensing import LicenseService


def encode(value: bytes) -> str:
    """Encode test token segments."""
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def signed_token(
    private_key: Ed25519PrivateKey,
    installation_id: str,
    *,
    valid_from: str,
    valid_until: str,
) -> str:
    """Issue a deterministic-shape test entitlement."""
    payload = {
        "license_id": str(uuid.uuid4()),
        "installation_id": installation_id,
        "customer_name": "Licensed Mandi Firm",
        "valid_from": valid_from,
        "valid_until": valid_until,
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return f"{encode(payload_bytes)}.{encode(private_key.sign(payload_bytes))}"


def test_signed_license_is_installation_bound_and_validated(tmp_path: Path) -> None:
    """Vendor signature and installation ID gate annual offline access."""
    databases = DatabaseManager(tmp_path / "licensed")
    databases.initialize()
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    payload = {
        "license_id": str(uuid.uuid4()),
        "installation_id": databases.installation_id(),
        "customer_name": "Licensed Mandi Firm",
        "valid_from": "2026-04-01",
        "valid_until": "2027-04-30",
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    token = f"{encode(payload_bytes)}.{encode(private_key.sign(payload_bytes))}"
    service = LicenseService(databases, public_pem)

    installed = service.install(token, today=date(2026, 10, 4))
    checked = service.status(today=date(2026, 10, 5))

    assert installed["valid"] is True
    assert checked["valid"] is True
    assert checked["customer_name"] == "Licensed Mandi Firm"


def test_license_warning_expiry_rollback_and_late_renewal(tmp_path: Path) -> None:
    """April warning remains writable, May locks writes, and renewal recovers."""
    databases = DatabaseManager(tmp_path / "phases")
    databases.initialize()
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    service = LicenseService(databases, public_pem)
    service.install(
        signed_token(
            private_key,
            databases.installation_id(),
            valid_from="2026-04-01",
            valid_until="2027-04-30",
        ),
        today=date(2026, 4, 1),
    )

    active = service.status(today=date(2027, 4, 10))
    warning = service.status(today=date(2027, 4, 11))
    final_day = service.status(today=date(2027, 4, 30))
    expired = service.status(today=date(2027, 5, 1))

    assert active["phase"] == "active" and active["writable"] is True
    assert warning["phase"] == "warning" and warning["writable"] is True
    assert warning["warning_message"] == (
        "Your subscription expires on 30-Apr-2027. "
        "Please renew to avoid service disruption."
    )
    assert final_day["phase"] == "warning" and final_day["writable"] is True
    assert expired["phase"] == "expired" and expired["writable"] is False
    with pytest.raises(LicenseWriteLockedError):
        service.assert_can_write(today=date(2027, 5, 1))

    service.install(
        signed_token(
            private_key,
            databases.installation_id(),
            valid_from="2027-05-20",
            valid_until="2028-04-30",
        ),
        today=date(2027, 5, 20),
    )
    renewed = service.assert_can_write(today=date(2027, 5, 20))
    assert renewed["phase"] == "active"
    assert renewed["valid_until"] == "2028-04-30"

    service.status(today=date(2027, 6, 1))
    with pytest.raises(ClockTamperException):
        service.assert_can_write(today=date(2027, 5, 31))


def test_expired_api_allows_history_but_rejects_writes(tmp_path: Path) -> None:
    """The bridge opens an expired company read-only and guards all mutations."""
    databases = DatabaseManager(tmp_path / "api-lock")
    databases.initialize()
    company = databases.create_company("Historical Firm", 2025)
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    service = LicenseService(databases, public_pem)
    current = date.today()
    expiry_year = current.year if (current.month, current.day) > (4, 30) else current.year - 1
    service.install(
        signed_token(
            private_key,
            databases.installation_id(),
            valid_from=f"{expiry_year - 1}-04-01",
            valid_until=f"{expiry_year}-04-30",
        ),
        today=current,
    )
    api = ApplicationApi(databases, service)
    company_id = str(company["company_id"])
    year_id = str(databases.list_financial_years(company_id)[0]["financial_year_id"])

    opened = api.select_context(company_id, year_id)
    blocked = api.create_account("Must Not Save", "expense")

    assert opened["ok"] is True
    assert blocked["ok"] is False
    assert blocked["error_type"] == "LicenseWriteLockedError"
