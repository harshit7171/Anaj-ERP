"""Resolve where catalog and company SQLite files live on disk.

Customer deployments use ``D:\\MandiERP\\Data`` or ``E:\\MandiERP\\Data`` when
that folder exists (created during site setup). Development and machines without
those folders fall back to the roaming application data directory. Override any
time with ``ANAJ_ERP_DATA_DIR`` or an explicit path passed to ``DatabaseManager``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

CUSTOMER_DATA_DIR_CANDIDATES: tuple[Path, ...] = (
    Path(r"D:\MandiERP\Data"),
    Path(r"E:\MandiERP\Data"),
)


@dataclass(frozen=True, slots=True)
class ResolvedDataDir:
    """Active data root and how it was chosen."""

    path: Path
    source: str


def _appdata_data_dir() -> Path:
    return Path(user_data_path("AnajERP", "AnajERP", roaming=True))


def resolve_data_dir(explicit: Path | str | None = None) -> Path:
    """Return the directory containing ``catalog.db`` and ``companies\\``."""
    return resolve_data_dir_with_source(explicit).path


def resolve_data_dir_with_source(explicit: Path | str | None = None) -> ResolvedDataDir:
    """Resolve the data root and record whether it came from env, D/E, or AppData."""
    if explicit is not None:
        return ResolvedDataDir(
            path=Path(explicit).expanduser().resolve(),
            source="explicit",
        )
    env = os.environ.get("ANAJ_ERP_DATA_DIR", "").strip()
    if env:
        return ResolvedDataDir(
            path=Path(env).expanduser().resolve(),
            source="environment",
        )
    for candidate in CUSTOMER_DATA_DIR_CANDIDATES:
        if candidate.is_dir():
            label = "customer_d" if candidate.drive.upper() == "D:" else "customer_e"
            return ResolvedDataDir(path=candidate.resolve(), source=label)
    return ResolvedDataDir(path=_appdata_data_dir().resolve(), source="appdata")
