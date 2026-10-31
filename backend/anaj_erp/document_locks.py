"""In-process document edit locks (single-PC standalone)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class LockRecord:
    resource_key: str
    holder: str
    holder_label: str
    acquired_at: float
    expires_at: float


class DocumentLockCoordinator:
    """TTL locks for vouchers/documents on one machine."""

    def __init__(self, ttl_seconds: float = 900.0) -> None:
        self._ttl = ttl_seconds
        self._guard = threading.RLock()
        self._locks: dict[str, LockRecord] = {}

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, record in self._locks.items() if record.expires_at <= now]
        for key in expired:
            self._locks.pop(key, None)

    def acquire(
        self,
        resource_key: str,
        holder: str,
        holder_label: str = "",
        *,
        ttl_seconds: float | None = None,
    ) -> dict[str, Any]:
        clean_key = str(resource_key or "").strip()
        if not clean_key:
            return {"ok": False, "error": "resource_key required"}
        holder_id = str(holder or "").strip()
        if not holder_id:
            return {"ok": False, "error": "holder required"}
        ttl = float(ttl_seconds if ttl_seconds is not None else self._ttl)
        now = time.monotonic()
        with self._guard:
            self._purge_expired()
            existing = self._locks.get(clean_key)
            if existing and existing.holder != holder_id:
                return {
                    "ok": False,
                    "locked": True,
                    "holder": existing.holder,
                    "holder_label": existing.holder_label,
                    "expires_in_seconds": max(0, int(existing.expires_at - now)),
                }
            record = LockRecord(
                resource_key=clean_key,
                holder=holder_id,
                holder_label=str(holder_label or holder_id),
                acquired_at=now,
                expires_at=now + ttl,
            )
            self._locks[clean_key] = record
            return {
                "ok": True,
                "resource_key": clean_key,
                "holder": holder_id,
                "expires_in_seconds": int(ttl),
            }

    def release(self, resource_key: str, holder: str) -> dict[str, Any]:
        clean_key = str(resource_key or "").strip()
        holder_id = str(holder or "").strip()
        with self._guard:
            self._purge_expired()
            existing = self._locks.get(clean_key)
            if existing is None:
                return {"ok": True, "released": False}
            if existing.holder != holder_id:
                return {"ok": False, "error": "Lock held by another session"}
            self._locks.pop(clean_key, None)
            return {"ok": True, "released": True}

    def status(self, resource_key: str) -> dict[str, Any]:
        clean_key = str(resource_key or "").strip()
        with self._guard:
            self._purge_expired()
            existing = self._locks.get(clean_key)
            if existing is None:
                return {"ok": True, "locked": False}
            now = time.monotonic()
            return {
                "ok": True,
                "locked": True,
                "holder": existing.holder,
                "holder_label": existing.holder_label,
                "expires_in_seconds": max(0, int(existing.expires_at - now)),
            }

    def snapshot(self) -> list[dict[str, Any]]:
        with self._guard:
            self._purge_expired()
            now = time.monotonic()
            return [
                {
                    "resource_key": record.resource_key,
                    "holder": record.holder,
                    "holder_label": record.holder_label,
                    "expires_in_seconds": max(0, int(record.expires_at - now)),
                }
                for record in self._locks.values()
            ]
