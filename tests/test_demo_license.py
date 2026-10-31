"""15-day demo mode for fresh installations (Point 17)."""

from datetime import date
from datetime import timedelta
from pathlib import Path

from anaj_erp.database import DatabaseManager
from anaj_erp.errors import LicenseWriteLockedError
from anaj_erp.licensing import DEMO_DAYS
from anaj_erp.licensing import LicenseService


def test_demo_writable_then_expires(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "demo")
    databases.initialize()
    start = date(2026, 6, 1)
    with databases.connect(databases.catalog_path) as connection:
        connection.execute(
            "UPDATE installation SET demo_started_at = ?",
            (start.isoformat(),),
        )
    public_pem = (Path(__file__).resolve().parents[1] / "resources" / "license_public_key.pem").read_bytes()
    service = LicenseService(databases, public_pem)
    active = service.status(today=start)
    assert active["phase"] == "demo"
    assert active["writable"] is True
    service.assert_can_write(today=start)

    last_day = start + timedelta(days=DEMO_DAYS - 1)
    still = service.status(today=last_day)
    assert still["phase"] == "demo"

    expired = start + timedelta(days=DEMO_DAYS)
    locked = service.status(today=expired)
    assert locked["phase"] == "demo_expired"
    assert locked["writable"] is False
    try:
        service.assert_can_write(today=expired)
        raise AssertionError("expected write lock")
    except LicenseWriteLockedError:
        pass
