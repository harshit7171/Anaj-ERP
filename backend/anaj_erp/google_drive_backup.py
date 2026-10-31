"""Optional Google Drive backup: sync folder and/or service-account upload."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .errors import ValidationError


def mirror_to_sync_folder(backup_path: Path, sync_folder: str | None) -> dict[str, object]:
    """Copy backup into a local folder (e.g. Google Drive for desktop)."""
    target_root = str(sync_folder or "").strip()
    if not target_root:
        return {"mirrored": False}
    dest_dir = Path(target_root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not backup_path.is_file():
        raise ValidationError("Backup file was not created")
    dest = dest_dir / backup_path.name
    shutil.copy2(backup_path, dest)
    return {"mirrored": True, "sync_path": str(dest)}


def upload_service_account_backup(
    backup_path: Path,
    settings: dict[str, Any],
) -> dict[str, object]:
    """Upload backup file to Drive folder using a Google service account JSON key."""
    key_path = str(settings.get("google_service_account_json_path") or "").strip()
    folder_id = str(settings.get("google_drive_folder_id") or "").strip()
    if not settings.get("google_drive_enabled"):
        return {"uploaded": False, "reason": "disabled"}
    if not key_path or not folder_id:
        return {"uploaded": False, "reason": "missing_credentials"}
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise ValidationError(
            "Google Drive upload requires: pip install google-api-python-client google-auth"
        ) from exc
    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    metadata = {"name": backup_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(backup_path), resumable=True)
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, name, webViewLink")
        .execute()
    )
    return {
        "uploaded": True,
        "file_id": created.get("id"),
        "file_name": created.get("name"),
        "web_view_link": created.get("webViewLink"),
    }


def apply_google_drive_backup(backup_path: Path, settings: dict[str, Any]) -> dict[str, object]:
    """Run configured Google Drive backup steps after local backup."""
    result: dict[str, object] = {}
    sync = mirror_to_sync_folder(
        backup_path,
        str(settings.get("google_drive_sync_folder") or ""),
    )
    result.update(sync)
    upload = upload_service_account_backup(backup_path, settings)
    result.update(upload)
    return result
