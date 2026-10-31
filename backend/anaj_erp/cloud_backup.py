"""Encrypted cloud backup (.bak.enc) for Google Drive and Microsoft OneDrive."""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet, InvalidToken

from .backup import BackupService
from .errors import ValidationError

logger = logging.getLogger(__name__)

GOOGLE_DEVICE_AUTH = "https://oauth2.googleapis.com/device/code"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"

MS_DEVICE_AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"
MS_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MS_GRAPH_UPLOAD = "https://graph.microsoft.com/v1.0/me/drive/root:/{name}:/content"


def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_file(source: Path, destination: Path, passphrase: str) -> Path:
    """Encrypt a backup file to `.bak.enc` using a user passphrase."""
    if not source.is_file():
        raise ValidationError("Backup source file is missing")
    phrase = str(passphrase or "").strip()
    if len(phrase) < 8:
        raise ValidationError("Cloud backup passphrase must be at least 8 characters")
    salt = os.urandom(16)
    token = Fernet(_derive_fernet_key(phrase, salt))
    ciphertext = token.encrypt(source.read_bytes())
    destination = destination.with_suffix(".bak.enc")
    destination.write_bytes(salt + ciphertext)
    return destination


def decrypt_file(source: Path, destination: Path, passphrase: str) -> Path:
    raw = source.read_bytes()
    if len(raw) < 17:
        raise ValidationError("Encrypted backup is too short")
    salt, ciphertext = raw[:16], raw[16:]
    token = Fernet(_derive_fernet_key(str(passphrase or "").strip(), salt))
    try:
        plaintext = token.decrypt(ciphertext)
    except InvalidToken as exc:
        raise ValidationError("Wrong passphrase or corrupted encrypted backup") from exc
    destination.write_bytes(plaintext)
    return destination


def _http_form(url: str, fields: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "AnajERP/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def start_oauth_device_flow(provider: str, settings: dict[str, Any]) -> dict[str, Any]:
    provider_key = provider.strip().lower()
    if provider_key == "google":
        client_id = str(settings.get("google_oauth_client_id") or "").strip()
        if not client_id:
            raise ValidationError("Set google_oauth_client_id under Cloud Backup settings")
        payload = _http_form(
            GOOGLE_DEVICE_AUTH,
            {
                "client_id": client_id,
                "scope": "https://www.googleapis.com/auth/drive.file",
            },
        )
        return {
            "provider": "google",
            "device_code": payload.get("device_code"),
            "user_code": payload.get("user_code"),
            "verification_url": payload.get("verification_url"),
            "expires_in": payload.get("expires_in"),
            "interval": payload.get("interval", 5),
        }
    if provider_key in {"microsoft", "onedrive"}:
        client_id = str(settings.get("microsoft_oauth_client_id") or "").strip()
        if not client_id:
            raise ValidationError("Set microsoft_oauth_client_id under Cloud Backup settings")
        payload = _http_form(
            MS_DEVICE_AUTH,
            {
                "client_id": client_id,
                "scope": "Files.ReadWrite offline_access",
            },
        )
        return {
            "provider": "onedrive",
            "device_code": payload.get("device_code"),
            "user_code": payload.get("user_code"),
            "verification_url": payload.get("verification_uri"),
            "expires_in": payload.get("expires_in"),
            "interval": payload.get("interval", 5),
        }
    raise ValidationError("Unknown cloud provider (google or onedrive)")


def poll_oauth_device_flow(
    provider: str,
    device_code: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    provider_key = provider.strip().lower()
    code = str(device_code or "").strip()
    if not code:
        raise ValidationError("device_code required")
    if provider_key == "google":
        client_id = str(settings.get("google_oauth_client_id") or "").strip()
        client_secret = str(settings.get("google_oauth_client_secret") or "").strip()
        fields = {
            "client_id": client_id,
            "device_code": code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }
        if client_secret:
            fields["client_secret"] = client_secret
        payload = _http_form(GOOGLE_TOKEN, fields)
    elif provider_key in {"microsoft", "onedrive"}:
        client_id = str(settings.get("microsoft_oauth_client_id") or "").strip()
        payload = _http_form(
            MS_TOKEN,
            {
                "client_id": client_id,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": code,
            },
        )
        provider_key = "onedrive"
    else:
        raise ValidationError("Unknown cloud provider")
    if payload.get("error"):
        pending = payload.get("error") in {"authorization_pending", "slow_down"}
        return {"ok": False, "pending": pending, "error": str(payload.get("error"))}
    tokens = {
        "access_token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
    }
    key = "google_oauth_tokens" if provider_key == "google" else "onedrive_oauth_tokens"
    return {"ok": True, "provider": provider_key, "token_key": key, "tokens": tokens}


def _refresh_google_access(settings: dict[str, Any]) -> str:
    tokens = settings.get("google_oauth_tokens")
    if not isinstance(tokens, dict):
        raise ValidationError("Google OAuth not linked — use device login in Cloud Backup")
    refresh = str(tokens.get("refresh_token") or "").strip()
    if not refresh:
        access = str(tokens.get("access_token") or "").strip()
        if access:
            return access
        raise ValidationError("Google refresh token missing — re-link OAuth")
    payload = _http_form(
        GOOGLE_TOKEN,
        {
            "client_id": str(settings.get("google_oauth_client_id") or ""),
            "client_secret": str(settings.get("google_oauth_client_secret") or ""),
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        },
    )
    access = str(payload.get("access_token") or "").strip()
    if not access:
        raise ValidationError("Google token refresh failed")
    return access


def _refresh_onedrive_access(settings: dict[str, Any]) -> str:
    tokens = settings.get("onedrive_oauth_tokens")
    if not isinstance(tokens, dict):
        raise ValidationError("OneDrive OAuth not linked")
    refresh = str(tokens.get("refresh_token") or "").strip()
    if not refresh:
        access = str(tokens.get("access_token") or "").strip()
        if access:
            return access
        raise ValidationError("OneDrive refresh token missing — re-link OAuth")
    payload = _http_form(
        MS_TOKEN,
        {
            "client_id": str(settings.get("microsoft_oauth_client_id") or ""),
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "scope": "Files.ReadWrite offline_access",
        },
    )
    access = str(payload.get("access_token") or "").strip()
    if not access:
        raise ValidationError("OneDrive token refresh failed")
    return access


def upload_encrypted_backup(
    encrypted_path: Path,
    settings: dict[str, Any],
) -> dict[str, object]:
    """Upload `.bak.enc` using OAuth tokens or local sync folders."""
    results: dict[str, object] = {"encrypted_path": str(encrypted_path)}
    folder = str(settings.get("cloud_backup_folder_name") or "AnajERP-Backups").strip()
    providers = settings.get("cloud_backup_providers")
    enabled = providers if isinstance(providers, list) else []
    if not enabled:
        if settings.get("cloud_backup_google_enabled"):
            enabled = ["google"]
        if settings.get("cloud_backup_onedrive_enabled"):
            enabled = list(enabled) + ["onedrive"]
    for provider in enabled:
        key = str(provider).lower()
        if key == "google":
            sync = str(settings.get("google_drive_sync_folder") or "").strip()
            if sync:
                dest_dir = Path(sync) / folder
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / encrypted_path.name
                shutil.copy2(encrypted_path, dest)
                results["google_sync_path"] = str(dest)
            if settings.get("google_oauth_tokens"):
                access = _refresh_google_access(settings)
                _upload_google_drive(access, encrypted_path, folder)
                results["google_uploaded"] = True
        elif key in {"microsoft", "onedrive"}:
            sync = str(settings.get("onedrive_sync_folder") or "").strip()
            if sync:
                dest_dir = Path(sync) / folder
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / encrypted_path.name
                shutil.copy2(encrypted_path, dest)
                results["onedrive_sync_path"] = str(dest)
            if settings.get("onedrive_oauth_tokens"):
                access = _refresh_onedrive_access(settings)
                _upload_onedrive(access, encrypted_path, folder)
                results["onedrive_uploaded"] = True
    return results


def _upload_google_drive(access_token: str, path: Path, folder_name: str) -> None:
    boundary = f"anaj-{secrets.token_hex(8)}"
    metadata = json.dumps({"name": path.name, "parents": []}).encode("utf-8")
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode("utf-8") + metadata + (
        f"\r\n--{boundary}\r\n"
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        GOOGLE_UPLOAD,
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "User-Agent": "AnajERP/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        if int(response.status) >= 300:
            raise ValidationError("Google Drive upload failed")


def _upload_onedrive(access_token: str, path: Path, folder_name: str) -> None:
    remote_name = urllib.parse.quote(f"{folder_name}/{path.name}")
    url = MS_GRAPH_UPLOAD.format(name=remote_name)
    request = urllib.request.Request(
        url,
        data=path.read_bytes(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "AnajERP/1.0",
        },
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        if int(response.status) >= 300:
            raise ValidationError("OneDrive upload failed")


def run_exit_cloud_backup(
    databases: Any,
    company_id: str,
    settings: dict[str, Any],
    destination_dir: Path,
) -> dict[str, object]:
    """Create encrypted snapshot and upload when cloud backup on exit is enabled."""
    if not settings.get("cloud_backup_on_exit"):
        return {"ok": True, "skipped": True}
    passphrase = str(settings.get("cloud_backup_passphrase") or "").strip()
    if len(passphrase) < 8:
        return {"ok": True, "skipped": True, "reason": "cloud_backup_passphrase not configured"}
    destination_dir.mkdir(parents=True, exist_ok=True)
    backup_path = BackupService(databases).create_company_backup(company_id, destination_dir)
    encrypted = encrypt_file(
        backup_path,
        destination_dir / f"{backup_path.stem}-{secrets.token_hex(4)}.bak.enc",
        passphrase,
    )
    upload = upload_encrypted_backup(encrypted, settings)
    return {"ok": True, "encrypted_path": str(encrypted), **upload}
