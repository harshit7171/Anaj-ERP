"""ESC/POS text builder for 80-column and 132-column dot-matrix printers."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import ValidationError

ESC = b"\x1b"
GS = b"\x1d"

COPY_LABELS = (
    ("farmer", "COPY 1 — FARMER / KISAN RECORD"),
    ("mandi", "COPY 2 — MANDI BOARD / APMC"),
    ("arhtiya", "COPY 3 — ARHTIYA (COMMISSION AGENT)"),
)


class EscPosBuilder:
    """Build raw ESC/POS byte streams (Epson / TVS MSP compatible subset)."""

    def __init__(self, *, columns: int = 80) -> None:
        if columns not in {80, 132}:
            raise ValidationError("ESC/POS width must be 80 or 132 columns")
        self.columns = columns
        self._width = 42 if columns == 80 else 72
        self._buffer = bytearray()
        self.init()

    def init(self) -> None:
        self._buffer.extend(ESC + b"@")

    def text(self, line: str) -> None:
        clean = line.replace("\r", "").replace("\n", " ")[: self._width]
        self._buffer.extend(clean.encode("cp437", errors="replace"))
        self._buffer.extend(b"\n")

    def bold(self, enabled: bool = True) -> None:
        self._buffer.extend(ESC + b"E" + (b"\x01" if enabled else b"\x00"))

    def double_height(self, enabled: bool = True) -> None:
        if enabled:
            self._buffer.extend(GS + b"!" + b"\x11")
        else:
            self._buffer.extend(GS + b"!" + b"\x00")

    def rule(self, char: str = "-") -> None:
        self.text(char * self._width)

    def feed(self, lines: int = 3) -> None:
        self._buffer.extend(ESC + b"d" + bytes([max(0, min(lines, 255))]))

    def cut(self) -> None:
        self._buffer.extend(GS + b"V" + b"\x00")

    def to_bytes(self) -> bytes:
        return bytes(self._buffer)


def spool_escpos_raw(data: bytes, destination: Path) -> Path:
    """Write raw ESC/POS to a spool file (copy to LPT/USB raw queue on Windows)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def try_windows_raw_print(data: bytes, printer_name: str | None = None) -> bool:
    """Send bytes to a named Windows printer when pywin32 is available."""
    if os.name != "nt":
        return False
    try:
        import win32print  # type: ignore[import-untyped]
    except ImportError:
        return False
    name = printer_name or win32print.GetDefaultPrinter()
    handle = win32print.OpenPrinter(name)
    try:
        job = win32print.StartDocPrinter(handle, 1, ("Anaj ERP ESC/POS", None, "RAW"))
        win32print.StartPagePrinter(handle)
        win32print.WritePrinter(handle, data)
        win32print.EndPagePrinter(handle)
        win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)
    return True
