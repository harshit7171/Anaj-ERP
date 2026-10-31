"""Tests for modular SQLite data directory resolution."""

from pathlib import Path

import pytest

from anaj_erp.data_paths import CUSTOMER_DATA_DIR_CANDIDATES
from anaj_erp.data_paths import resolve_data_dir
from anaj_erp.data_paths import resolve_data_dir_with_source
from anaj_erp.database import DatabaseManager
from anaj_erp.database import configure_sqlite_connection
import sqlite3


def test_resolve_prefers_environment_over_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ANAJ_ERP_DATA_DIR overrides D/E and AppData."""
    env_root = tmp_path / "from-env"
    env_root.mkdir()
    monkeypatch.setenv("ANAJ_ERP_DATA_DIR", str(env_root))
    assert resolve_data_dir() == env_root.resolve()
    assert resolve_data_dir_with_source().source == "environment"


def test_resolve_uses_existing_customer_folder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """First existing MandiERP Data candidate wins when env is unset."""
    monkeypatch.delenv("ANAJ_ERP_DATA_DIR", raising=False)
    customer = tmp_path / "MandiERP" / "Data"
    customer.mkdir(parents=True)
    monkeypatch.setattr(
        "anaj_erp.data_paths.CUSTOMER_DATA_DIR_CANDIDATES",
        (customer, tmp_path / "unused"),
    )
    resolved = resolve_data_dir_with_source()
    assert resolved.path == customer.resolve()
    assert resolved.source in {"customer_d", "customer_e"}


def test_resolve_falls_back_to_appdata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When no env or customer folder exists, use roaming AppData."""
    monkeypatch.delenv("ANAJ_ERP_DATA_DIR", raising=False)
    monkeypatch.setattr(
        "anaj_erp.data_paths.CUSTOMER_DATA_DIR_CANDIDATES",
        (tmp_path / "missing-d", tmp_path / "missing-e"),
    )
    appdata = tmp_path / "Roaming" / "AnajERP"
    monkeypatch.setattr(
        "anaj_erp.data_paths._appdata_data_dir",
        lambda: appdata,
    )
    assert resolve_data_dir() == appdata.resolve()
    assert resolve_data_dir_with_source().source == "appdata"


def test_database_manager_uses_explicit_path(tmp_path: Path) -> None:
    """Tests and tools can pin an isolated data root."""
    root = tmp_path / "isolated"
    manager = DatabaseManager(root)
    assert manager.data_dir == root.resolve()


def test_sqlite_connection_applies_standard_pragmas(tmp_path: Path) -> None:
    """Every connection uses WAL, NORMAL synchronous, and foreign keys."""
    db_path = tmp_path / "pragma.db"
    with sqlite3.connect(db_path) as connection:
        configure_sqlite_connection(connection)
        journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    assert journal.lower() == "wal"
    assert synchronous == 1  # NORMAL
    assert foreign_keys == 1


def test_customer_candidates_use_d_and_e_drives() -> None:
    """Documented customer paths remain D and E MandiERP Data."""
    drives = {path.drive.upper() for path in CUSTOMER_DATA_DIR_CANDIDATES}
    assert drives == {"D:", "E:"}
