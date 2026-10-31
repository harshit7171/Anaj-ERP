"""Print statutory mandi HTML through the active pywebview window."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def print_html_file(path: Path, *, silent: bool = False) -> bool:
    """Load HTML in a hidden iframe and invoke the WebView print path.

    Note:
        WebView2 may still show a system print dialog unless the job is sent as
        ESC/POS raw (see ``print_mandi_bill`` with ``use_escpos=True``).
        ``silent=True`` skips ``window.print()`` and only materializes the file
        for raw / driver-specific spoolers.
    """
    if silent:
        return path.is_file()
    try:
        import webview
    except ImportError:
        return False
    windows = getattr(webview, "windows", None)
    if not windows:
        return False
    window = windows[0]
    uri = path.resolve().as_uri()
    script = f"""
    (function () {{
      var frame = document.createElement('iframe');
      frame.style.position = 'fixed';
      frame.style.right = '0';
      frame.style.bottom = '0';
      frame.style.width = '0';
      frame.style.height = '0';
      frame.style.border = '0';
      frame.src = {json.dumps(uri)};
      document.body.appendChild(frame);
      frame.onload = function () {{
        try {{
          frame.contentWindow.focus();
          frame.contentWindow.print();
        }} catch (e) {{ console.error(e); }}
      }};
    }})();
    """
    try:
        window.evaluate_js(script)
        return True
    except Exception:
        logger.exception("WebView HTML print failed")
        return False
