"""UDP office LAN discovery — master PC advertises HTTP/WebSocket endpoints."""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

BEACON_MAGIC = "ANAJERP1"
DEFAULT_DISCOVERY_PORT = 8766


@dataclass(frozen=True)
class OfficeBeacon:
    """Parsed master announcement."""

    host: str
    http_port: int
    office_name: str
    ws_path: str = "/ws/live"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.http_port}"

    def to_dict(self) -> dict[str, object]:
        return {
            "host": self.host,
            "http_port": self.http_port,
            "office_name": self.office_name,
            "url": self.base_url,
            "ws_url": f"ws://{self.host}:{self.http_port}{self.ws_path}",
        }


def _encode_beacon(host: str, http_port: int, office_name: str) -> bytes:
    payload = {
        "magic": BEACON_MAGIC,
        "host": host,
        "http_port": http_port,
        "office_name": office_name,
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def parse_beacon(raw: bytes, source_host: str) -> OfficeBeacon | None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("magic") != BEACON_MAGIC:
        return None
    port = int(data.get("http_port") or 8765)
    name = str(data.get("office_name") or "Anaj ERP Office")
    host = str(data.get("host") or source_host).strip() or source_host
    return OfficeBeacon(host=host, http_port=port, office_name=name)


class DiscoveryBroadcaster:
    """Send periodic UDP broadcasts on the office LAN."""

    def __init__(
        self,
        http_port: int,
        office_name: str,
        *,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        bind_host: str = "0.0.0.0",
    ) -> None:
        self.http_port = http_port
        self.office_name = office_name
        self.discovery_port = discovery_port
        self.bind_host = bind_host
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="anaj-lan-beacon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        advertise_host = _local_ipv4()
        packet = _encode_beacon(advertise_host, self.http_port, self.office_name)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self._stop.is_set():
                try:
                    sock.sendto(packet, ("<broadcast>", self.discovery_port))
                except OSError as exc:
                    logger.debug("LAN beacon send failed: %s", exc)
                self._stop.wait(3.0)


def discover_offices(timeout_seconds: float = 2.5) -> list[dict[str, object]]:
    """Listen for master UDP beacons (desktop or Munim laptop on same Wi-Fi)."""
    found: dict[str, OfficeBeacon] = {}
    deadline = time.monotonic() + max(0.5, timeout_seconds)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DEFAULT_DISCOVERY_PORT))
        sock.settimeout(0.4)
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
            except TimeoutError:
                continue
            beacon = parse_beacon(data, addr[0])
            if beacon is None:
                continue
            found[f"{beacon.host}:{beacon.http_port}"] = beacon
    return [beacon.to_dict() for beacon in sorted(found.values(), key=lambda b: b.office_name)]


def _local_ipv4() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"


def office_beacon_payload(office_name: str, http_port: int) -> dict[str, Any]:
    host = _local_ipv4()
    return {
        "magic": BEACON_MAGIC,
        "office_name": office_name,
        "host": host,
        "http_port": http_port,
        "url": f"http://{host}:{http_port}",
        "ws_url": f"ws://{host}:{http_port}/ws/live",
        "discovery_port": DEFAULT_DISCOVERY_PORT,
    }
