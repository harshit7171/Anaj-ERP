"""Fleet registry issue and revoke (Point 35)."""

from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from anaj_erp.fleet_licensing import FleetRegistry
from anaj_erp.licensing import LicenseService


def test_fleet_issue_and_revoke(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fleet = FleetRegistry(tmp_path / "fleet.db")
    installation_id = "11111111-2222-3333-4444-555555555555"
    fleet.heartbeat(installation_id, "ABC Traders")
    token = fleet.issue_license_token(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        installation_id=installation_id,
        customer_name="ABC Traders",
        valid_from="2026-04-01",
        valid_until="2027-04-30",
        features=["GRAIN", "MULTI_USER"],
    )
    assert "." in token
    databases_dir = tmp_path / "client"
    databases_dir.mkdir()
    from anaj_erp.database import DatabaseManager

    databases = DatabaseManager(databases_dir)
    databases.initialize()
    with databases.connect(databases.catalog_path) as connection:
        connection.execute(
            "UPDATE installation SET installation_id = ?",
            (installation_id,),
        )
    license_service = LicenseService(databases, public_pem)
    license_service.install(token, today=date(2026, 10, 1))
    status = license_service.status(today=date(2026, 10, 2))
    assert status["valid"] is True
    assert "GRAIN" in status.get("features", [])

    fleet.revoke(installation_id, revoked=True)
    beat = fleet.heartbeat(installation_id, "ABC Traders")
    assert beat["ok"] is False
