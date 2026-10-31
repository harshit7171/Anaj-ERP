#!/usr/bin/env python3
"""Issue a signed offline license token (vendor private key — keep secret)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from anaj_erp.fleet_licensing import FleetRegistry  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Sign Anaj ERP license payload")
    parser.add_argument("--private-key-pem", required=True, help="Ed25519 private key PEM path")
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--customer-name", required=True)
    parser.add_argument("--valid-from", required=True, help="ISO date YYYY-MM-DD")
    parser.add_argument("--valid-until", required=True, help="Must end April 30 for annual")
    parser.add_argument("--features", default="GRAIN,MULTI_USER")
    parser.add_argument("--fleet-db", default="fleet/fleet.db")
    args = parser.parse_args()

    registry = FleetRegistry(Path(args.fleet_db))
    token = registry.issue_license_token(
        Path(args.private_key_pem).read_bytes(),
        installation_id=args.installation_id,
        customer_name=args.customer_name,
        valid_from=args.valid_from,
        valid_until=args.valid_until,
        features=[part.strip() for part in args.features.split(",") if part.strip()],
    )
    print(token)


if __name__ == "__main__":
    main()
