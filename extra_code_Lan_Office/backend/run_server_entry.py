"""Console entry for `anaj-erp-server`."""

from __future__ import annotations

import logging
import os

from .data_paths import resolve_data_dir_with_source


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            'Missing server dependencies. Run: pip install -e ".[server]"'
        ) from exc

    from .lan_server import create_app

    resolved = resolve_data_dir_with_source()
    logging.getLogger(__name__).info(
        "LAN server data directory: %s (%s)", resolved.path, resolved.source
    )
    root = resolved.path
    host = os.environ.get("ANAJ_ERP_HOST", "0.0.0.0")
    port = int(os.environ.get("ANAJ_ERP_PORT", "8765"))
    application = create_app(root)
    uvicorn.run(application, host=host, port=port, log_level="info")
