"""Vendor-only CLI for generating keys and issuing offline annual licenses.

This tool is not included in the customer installer. Its private key is stored
outside the repository and protected with Windows DPAPI for the vendor user.
"""

from __future__ import annotations

import argparse
import base64
import json
import uuid
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from platformdirs import user_data_path

from anaj_erp.security import protect_for_current_user
from anaj_erp.security import unprotect_for_current_user


def encode(value: bytes) -> str:
    """Encode one URL-safe license segment."""
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def default_private_path() -> Path:
    """Return vendor-only protected private-key storage."""
    return Path(user_data_path("AnajERPVendor", "AnajERP")) / "vendor_private_key.dpapi"


def initialize_keys(private_path: Path, public_path: Path) -> None:
    """Generate a vendor signing key pair without writing plaintext private data."""
    if private_path.exists() or public_path.exists():
        raise FileExistsError("Refusing to overwrite existing vendor keys")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    private_path.write_bytes(protect_for_current_user(private_raw))
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def issue_license(
    private_path: Path,
    installation_id: str,
    customer_name: str,
    start_year: int,
) -> str:
    """Issue a signed April-through-April annual license token."""
    private_raw = unprotect_for_current_user(private_path.read_bytes())
    private_key = Ed25519PrivateKey.from_private_bytes(private_raw)
    payload = {
        "license_id": str(uuid.uuid4()),
        "installation_id": installation_id,
        "customer_name": customer_name.strip(),
        "valid_from": date(start_year, 4, 1).isoformat(),
        "valid_until": date(start_year + 1, 4, 30).isoformat(),
        "issued_at": date.today().isoformat(),
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return f"{encode(payload_bytes)}.{encode(private_key.sign(payload_bytes))}"


def main() -> None:
    """Parse vendor key administration commands."""
    parser = argparse.ArgumentParser(description="Anaj ERP offline license administration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize = subparsers.add_parser("init", help="Generate vendor signing keys")
    initialize.add_argument(
        "--private",
        type=Path,
        default=default_private_path(),
    )
    initialize.add_argument("--public", type=Path, required=True)
    issue = subparsers.add_parser("issue", help="Issue one installation-bound license")
    issue.add_argument(
        "--private",
        type=Path,
        default=default_private_path(),
    )
    issue.add_argument("--installation-id", required=True)
    issue.add_argument("--customer", required=True)
    issue.add_argument("--start-year", required=True, type=int)
    issue.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "init":
        initialize_keys(args.private, args.public)
        return
    token = issue_license(
        args.private,
        args.installation_id,
        args.customer,
        args.start_year,
    )
    if args.output:
        args.output.write_text(token, encoding="utf-8")
    else:
        print(token)


if __name__ == "__main__":
    main()
