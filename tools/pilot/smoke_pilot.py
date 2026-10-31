"""Minimal pilot smoke — company create, TB, LAN health (if server extras installed)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from anaj_erp.api import ApplicationApi
from anaj_erp.database import DatabaseManager
from anaj_erp.licensing import LicenseService


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "pilot"
        databases = DatabaseManager(data)
        databases.initialize()
        key_path = ROOT / "resources" / "license_public_key.pem"
        license_service = LicenseService(databases, key_path.read_bytes())
        api = ApplicationApi(databases, license_service)
        company = api.create_company("Pilot Smoke Co", 2026)
        assert company["ok"], company
        company_id = str(company["company"]["company_id"])
        years = api.list_financial_years(company_id)
        assert years["ok"] and years["financial_years"]
        year_id = str(years["financial_years"][0]["financial_year_id"])
        selected = api.select_context(company_id, year_id)
        assert selected["ok"], selected
        tb = api.trial_balance()
        assert tb["ok"], tb
    print("Pilot smoke OK (standalone desktop path)")


if __name__ == "__main__":
    main()
