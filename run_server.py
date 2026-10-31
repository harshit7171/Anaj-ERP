"""LAN office server launcher (archived — standalone app does not use this)."""

from __future__ import annotations

import sys


def main() -> None:
    print(
        "The office LAN server has moved to extra_code_Lan_Office/.\n"
        "The desktop ERP runs standalone on a single PC by default.\n"
        "See extra_code_Lan_Office/README.md to restore LAN mode.",
        file=sys.stderr,
    )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
