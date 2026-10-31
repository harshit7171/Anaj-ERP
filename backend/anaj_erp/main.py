"""Windows desktop entry point for the offline Anaj ERP."""

from __future__ import annotations

import http.server
import logging
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
from functools import partial
from logging.handlers import RotatingFileHandler
from pathlib import Path

import webview
from platformdirs import user_log_path

from .api import ApplicationApi
from .data_paths import resolve_data_dir_with_source
from .database import DatabaseManager
from .licensing import LicenseService

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure bounded local logs without storing financial payloads."""
    log_dir = Path(user_log_path("AnajERP", "AnajERP"))
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "anaj-erp.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def _dev_server_reachable(url: str) -> bool:
    """Return True when the Vite dev server responds."""
    probe = url.rstrip("/") + "/"
    try:
        with urllib.request.urlopen(probe, timeout=2) as response:
            return int(response.status) == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_dist_http_server(dist_dir: Path) -> tuple[str, http.server.ThreadingHTTPServer]:
    """Serve built frontend over http:// — file:// breaks ES modules in WebView2."""
    port = _free_port()
    handler = partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(dist_dir.resolve()),
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/index.html"
    logger.info("Serving frontend dist", extra={"url": url, "dist": str(dist_dir)})
    return url, server


def frontend_location() -> tuple[str, http.server.ThreadingHTTPServer | None]:
    """Resolve a http(s) URL for pywebview (never file:// for production builds).

    Returns:
        Tuple of load URL and optional dist server handle to keep alive.

    Raises:
        FileNotFoundError: If production assets have not been built.
    """
    project_root = Path(__file__).resolve().parents[2]
    dist_dir = project_root / "frontend" / "dist"
    development_url = os.environ.get("ANAJ_ERP_DEV_URL", "").strip()
    if development_url and _dev_server_reachable(development_url):
        logger.info("Using Vite dev server", extra={"url": development_url})
        return development_url.rstrip("/") + "/", None
    if development_url:
        logger.warning(
            "ANAJ_ERP_DEV_URL is set but dev server is not reachable; using production build",
            extra={"url": development_url},
        )
    index_path = dist_dir / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(
            "Frontend build is missing. Run `npm run build` before launching, "
            "or start Vite with npm run dev and set ANAJ_ERP_DEV_URL."
        )
    return _start_dist_http_server(dist_dir)


def resource_path(relative_path: str) -> Path:
    """Resolve a resource from source tree or a PyInstaller bundle."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return bundle_root / relative_path


def main() -> None:
    """Initialize local storage and launch the desktop window."""
    configure_logging()
    resolved = resolve_data_dir_with_source()
    logger.info(
        "Using data directory",
        extra={"path": str(resolved.path), "source": resolved.source},
    )
    databases = DatabaseManager(resolved.path)
    databases.initialize()
    public_key_path = resource_path("resources/license_public_key.pem")
    if not public_key_path.exists():
        raise FileNotFoundError("Vendor license public key is missing")
    license_service = LicenseService(databases, public_key_path.read_bytes())
    startup_license = license_service.status()
    if startup_license.get("phase") == "clock_tamper":
        logger.error("System clock rollback detected; business sessions are frozen")
    api = ApplicationApi(databases, license_service)
    load_url, dist_server = frontend_location()
    logger.info("Starting Anaj ERP desktop", extra={"url": load_url})
    webview.create_window(
        "Anaj Accounting ERP",
        load_url,
        js_api=api,
        width=1280,
        height=760,
        min_size=(1024, 640),
        confirm_close=True,
    )
    debug = os.environ.get("ANAJ_ERP_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    try:
        webview.start(debug=debug, private_mode=False)
    finally:
        try:
            exit_backup = api.run_exit_cloud_backup_if_enabled()
            if exit_backup.get("ok") and not exit_backup.get("skipped"):
                logger.info(
                    "Exit cloud backup finished",
                    extra={"path": exit_backup.get("encrypted_path")},
                )
        except Exception:
            logger.exception("Exit cloud backup failed")
        if dist_server is not None:
            dist_server.shutdown()


if __name__ == "__main__":
    main()
