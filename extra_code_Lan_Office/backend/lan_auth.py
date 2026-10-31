"""Office LAN users and bearer sessions stored in the installation catalog."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from typing import Any

from .database import DatabaseManager
from .database import utc_now
from .errors import ValidationError

CATALOG_USER_SQL = """
CREATE TABLE IF NOT EXISTS app_user (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'munim', 'operator', 'clerk', 'readonly')),
    can_view_kachi INTEGER NOT NULL DEFAULT 0 CHECK (can_view_kachi IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_session (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES app_user(user_id)
);

CREATE INDEX IF NOT EXISTS ix_app_session_user ON app_session(user_id, expires_at);
"""

VALID_ROLES = frozenset({"admin", "munim", "operator", "clerk", "readonly"})


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return a salted scrypt hash suitable for catalog storage."""
    if not password:
        raise ValidationError("Password is required")
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt_bytes,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Compare a plaintext password with a stored scrypt hash."""
    try:
        scheme, salt_hex, digest_hex = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    candidate = hash_password(password, salt=bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, stored)


def default_can_view_kachi(role: str) -> bool:
    """Munim/admin typically see Kachi books; clerks do not by default."""
    return role in {"admin", "munim"}


class UserService:
    """Manage LAN users in the installation catalog."""

    def __init__(self, databases: DatabaseManager) -> None:
        self.databases = databases

    def ensure_schema(self) -> None:
        with self.databases.connect(self.databases.catalog_path) as connection:
            connection.executescript(CATALOG_USER_SQL)

    def bootstrap_admin_if_empty(self, password: str) -> dict[str, str] | None:
        """Create the first admin when no users exist (server first run)."""
        self.ensure_schema()
        with self.databases.connect(self.databases.catalog_path) as connection:
            count = connection.execute("SELECT COUNT(*) AS c FROM app_user").fetchone()
            if count is None or int(count["c"]) > 0:
                return None
            user_id = str(uuid.uuid4())
            timestamp = utc_now()
            connection.execute(
                """
                INSERT INTO app_user(
                    user_id, username, password_hash, display_name, role,
                    can_view_kachi, is_active, created_at, updated_at
                ) VALUES (?, 'admin', ?, 'Administrator', 'admin', 1, 1, ?, ?)
                """,
                (user_id, hash_password(password), timestamp, timestamp),
            )
        return {"username": "admin", "user_id": user_id}

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        clean = username.strip()
        if not clean or not password:
            raise ValidationError("Username and password are required")
        self.ensure_schema()
        with self.databases.connect(self.databases.catalog_path) as connection:
            row = connection.execute(
                """
                SELECT user_id, username, password_hash, display_name, role,
                    can_view_kachi, is_active
                FROM app_user
                WHERE username = ? COLLATE NOCASE
                """,
                (clean,),
            ).fetchone()
        if row is None or int(row["is_active"]) != 1:
            raise ValidationError("Invalid username or password")
        if not verify_password(password, str(row["password_hash"])):
            raise ValidationError("Invalid username or password")
        token = secrets.token_urlsafe(32)
        session_id = str(uuid.uuid4())
        from datetime import UTC, datetime, timedelta

        expires = (datetime.now(UTC) + timedelta(hours=12)).isoformat(timespec="seconds")
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        timestamp = utc_now()
        with self.databases.connect(self.databases.catalog_path) as connection:
            connection.execute(
                """
                INSERT INTO app_session(session_id, user_id, token_hash, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, str(row["user_id"]), token_hash, expires, timestamp),
            )
        return {
            "token": token,
            "expires_at": expires,
            "user": {
                "user_id": str(row["user_id"]),
                "username": str(row["username"]),
                "display_name": str(row["display_name"]),
                "role": str(row["role"]),
                "can_view_kachi": bool(int(row["can_view_kachi"])),
            },
        }

    def resolve_token(self, token: str) -> dict[str, Any]:
        if not token.strip():
            raise ValidationError("Missing session token")
        token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        self.ensure_schema()
        with self.databases.connect(self.databases.catalog_path) as connection:
            row = connection.execute(
                """
                SELECT
                    s.session_id, s.expires_at,
                    u.user_id, u.username, u.display_name, u.role,
                    u.can_view_kachi, u.is_active
                FROM app_session s
                JOIN app_user u ON u.user_id = s.user_id
                WHERE s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        if row is None or int(row["is_active"]) != 1:
            raise ValidationError("Session expired or invalid")
        if str(row["expires_at"]) < utc_now():
            raise ValidationError("Session expired or invalid")
        return {
            "user_id": str(row["user_id"]),
            "username": str(row["username"]),
            "display_name": str(row["display_name"]),
            "role": str(row["role"]),
            "can_view_kachi": bool(int(row["can_view_kachi"])),
        }

    def list_users(self) -> list[dict[str, Any]]:
        self.ensure_schema()
        with self.databases.connect(self.databases.catalog_path) as connection:
            rows = connection.execute(
                """
                SELECT user_id, username, display_name, role, can_view_kachi, is_active,
                    created_at, updated_at
                FROM app_user
                ORDER BY username COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def save_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        username = str(payload.get("username", "")).strip()
        display_name = str(payload.get("display_name", "")).strip() or username
        role = str(payload.get("role", "clerk")).strip().lower()
        if role not in VALID_ROLES:
            raise ValidationError("Invalid role")
        user_id = str(payload.get("user_id") or uuid.uuid4())
        can_view = payload.get("can_view_kachi")
        if can_view is None:
            can_view_kachi = default_can_view_kachi(role)
        else:
            can_view_kachi = bool(can_view)
        is_active = 1 if payload.get("is_active", True) else 0
        password = str(payload.get("password", "")).strip()
        timestamp = utc_now()
        self.ensure_schema()
        with self.databases.connect(self.databases.catalog_path) as connection:
            existing = connection.execute(
                "SELECT user_id FROM app_user WHERE username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
            if existing is not None and str(existing["user_id"]) != user_id:
                raise ValidationError("Username already exists")
            if connection.execute(
                "SELECT 1 FROM app_user WHERE user_id = ?", (user_id,)
            ).fetchone():
                if password:
                    password_hash = hash_password(password)
                    connection.execute(
                        """
                        UPDATE app_user SET
                            username = ?, display_name = ?, role = ?,
                            can_view_kachi = ?, is_active = ?,
                            password_hash = ?, updated_at = ?
                        WHERE user_id = ?
                        """,
                        (
                            username,
                            display_name,
                            role,
                            int(can_view_kachi),
                            is_active,
                            password_hash,
                            timestamp,
                            user_id,
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE app_user SET
                            username = ?, display_name = ?, role = ?,
                            can_view_kachi = ?, is_active = ?, updated_at = ?
                        WHERE user_id = ?
                        """,
                        (
                            username,
                            display_name,
                            role,
                            int(can_view_kachi),
                            is_active,
                            timestamp,
                            user_id,
                        ),
                    )
            else:
                if not password:
                    raise ValidationError("Password is required for new users")
                connection.execute(
                    """
                    INSERT INTO app_user(
                        user_id, username, password_hash, display_name, role,
                        can_view_kachi, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        hash_password(password),
                        display_name,
                        role,
                        int(can_view_kachi),
                        is_active,
                        timestamp,
                        timestamp,
                    ),
                )
        return {
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "role": role,
            "can_view_kachi": can_view_kachi,
            "is_active": bool(is_active),
        }

    def set_company_profile(self, company_id: str, profile: str) -> dict[str, str]:
        clean = profile.strip().lower()
        if clean not in {"standard", "kachi"}:
            raise ValidationError("Company profile must be standard or kachi")
        with self.databases.connect(self.databases.catalog_path) as connection:
            updated = connection.execute(
                """
                UPDATE company_catalog
                SET company_profile = ?, updated_at = ?
                WHERE company_id = ? AND is_deleted = 0
                """,
                (clean, utc_now(), company_id),
            ).rowcount
        if updated != 1:
            raise ValidationError("Company not found")
        return {"company_id": company_id, "company_profile": clean}
