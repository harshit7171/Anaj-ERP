"""Console entry for vendor fleet licensing portal."""

from __future__ import annotations

import logging
import os


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit('Missing server extras: pip install -e ".[server]"') from exc

    from .fleet_portal import create_fleet_app

    host = os.environ.get("ANAJ_FLEET_HOST", "127.0.0.1")
    port = int(os.environ.get("ANAJ_FLEET_PORT", "8870"))
    uvicorn.run(create_fleet_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
