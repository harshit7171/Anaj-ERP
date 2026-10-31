"""Placeholder entry for deprecated `anaj-erp-server` console script."""

from __future__ import annotations

import sys


def main() -> None:
    print(
        "Office LAN server is archived under extra_code_Lan_Office/.\n"
        "Use the desktop app for single-PC standalone operation.",
        file=sys.stderr,
    )
    raise SystemExit(1)
