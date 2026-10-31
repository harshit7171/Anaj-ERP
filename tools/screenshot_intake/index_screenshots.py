"""Index reference ERP screenshots for parity and dialog extraction."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = ROOT / "screenshot" / "screenshot"
OUTPUT = ROOT / "docs" / "screenshot-index.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if not SCREENSHOT_DIR.is_dir():
        raise SystemExit(f"Screenshot directory missing: {SCREENSHOT_DIR}")

    entries: list[dict[str, object]] = []
    for path in sorted(SCREENSHOT_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
            continue
        stat = path.stat()
        entries.append(
            {
                "id": path.stem,
                "filename": path.name,
                "relative_path": path.relative_to(ROOT).as_posix(),
                "bytes": stat.st_size,
                "sha256": file_sha256(path),
            }
        )

    payload = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "source_dir": str(SCREENSHOT_DIR),
        "count": len(entries),
        "entries": entries,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Indexed {len(entries)} screenshots -> {OUTPUT}")


if __name__ == "__main__":
    main()
