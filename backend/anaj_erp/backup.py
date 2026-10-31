"""Consistent local backup and SQLite integrity verification."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import UTC
from datetime import datetime
from pathlib import Path

from .database import DatabaseManager
from .database import configure_sqlite_connection
from .database import utc_now
from .errors import DatabaseError
from .errors import ValidationError


class BackupService:
    """Create verified, portable backups without copying a live WAL database."""

    def __init__(self, databases: DatabaseManager) -> None:
        """Store the database manager used to resolve company files."""
        self.databases = databases

    @staticmethod
    def integrity_check(path: Path) -> None:
        """Run SQLite integrity and foreign-key checks.

        Raises:
            DatabaseError: If corruption or broken references are detected.
        """
        try:
            with closing(sqlite3.connect(path)) as connection:
                configure_sqlite_connection(connection)
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not verify database: {exc}") from exc
        if integrity is None or integrity[0] != "ok":
            raise DatabaseError(f"Database integrity check failed: {integrity}")
        if foreign_keys:
            raise DatabaseError(f"Database has {len(foreign_keys)} foreign-key errors")

    def create_company_backup(self, company_id: str, destination: Path) -> Path:
        """Create a checked ZIP backup using SQLite's online backup API.

        Args:
            company_id: Company catalog identifier.
            destination: Target `.anajbackup` path.

        Returns:
            Final backup path.
        """
        source_path = self.databases.company_path(company_id)
        destination = destination.with_suffix(".anajbackup")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="anaj-backup-") as temp_dir:
            snapshot_path = Path(temp_dir) / "company.db"
            try:
                with closing(sqlite3.connect(source_path)) as source:
                    configure_sqlite_connection(source)
                    with closing(sqlite3.connect(snapshot_path)) as snapshot:
                        configure_sqlite_connection(snapshot)
                        source.backup(snapshot)
            except sqlite3.Error as exc:
                raise DatabaseError(f"Backup snapshot failed: {exc}") from exc
            self.integrity_check(snapshot_path)
            content = snapshot_path.read_bytes()
            manifest = {
                "format_version": 1,
                "company_id": company_id,
                "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(content).hexdigest(),
                "database_filename": "company.db",
            }
            temporary_target = destination.with_suffix(".tmp")
            with zipfile.ZipFile(
                temporary_target,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, sort_keys=True, indent=2),
                )
                archive.writestr("company.db", content)
            temporary_target.replace(destination)
        return destination

    def restore_new_company(self, source: Path) -> dict[str, str]:
        """Restore a verified backup only when its company is not present.

        This is for disaster recovery or initial Home Laptop bootstrap. It is
        intentionally not a synchronization operation and never overwrites a
        live company database.
        """
        try:
            with zipfile.ZipFile(source) as archive:
                if set(archive.namelist()) != {"manifest.json", "company.db"}:
                    raise ValidationError("Backup contains unexpected files")
                manifest = json.loads(archive.read("manifest.json"))
                content = archive.read("company.db")
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            raise ValidationError("Backup package is invalid") from exc
        if hashlib.sha256(content).hexdigest() != manifest.get("sha256"):
            raise ValidationError("Backup checksum does not match")
        company_id = str(manifest.get("company_id", ""))
        if not company_id:
            raise ValidationError("Backup company identity is missing")
        with tempfile.TemporaryDirectory(prefix="anaj-restore-") as temp_dir:
            candidate = Path(temp_dir) / "company.db"
            candidate.write_bytes(content)
            self.integrity_check(candidate)
            with closing(sqlite3.connect(candidate)) as connection:
                configure_sqlite_connection(connection)
                row = connection.execute(
                    "SELECT company_id, name FROM company LIMIT 1"
                ).fetchone()
            if row is None or str(row[0]) != company_id:
                raise ValidationError("Backup company identity does not match its data")
            company_name = str(row[1])
            filename = f"{company_id}.db"
            destination = self.databases.companies_dir / filename
            with self.databases.connect(self.databases.catalog_path) as connection:
                existing = connection.execute(
                    "SELECT company_id FROM company_catalog WHERE company_id = ?",
                    (company_id,),
                ).fetchone()
                if existing is not None or destination.exists():
                    raise ValidationError(
                        "Company already exists; restore cannot overwrite live data"
                    )
                temporary_destination = destination.with_suffix(".restore")
                temporary_destination.write_bytes(content)
                self.integrity_check(temporary_destination)
                temporary_destination.replace(destination)
                timestamp = utc_now()
                connection.execute(
                    """
                    INSERT INTO company_catalog(
                        company_id, name, database_filename, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (company_id, company_name, filename, timestamp, timestamp),
                )
        return {"company_id": company_id, "name": company_name}
