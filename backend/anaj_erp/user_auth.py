"""Installation-catalog users and desktop sessions (standalone multi-user)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .database import DatabaseManager
from .database import utc_now
from .errors import ValidationError

VALID_ROLES = frozenset({"admin", "munim", "operator", "clerk", "readonly"})


def hash_password(password: str, *, salt: bytes | None = None) -> str:
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
    try:
        scheme, salt_hex, digest_hex = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    candidate = hash_password(password, salt=bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, stored)


def default_can_view_kachi(role: str) -> bool:
    return role in {"admin", "munim"}


def _parse_until(value: str | None) -> str | None:
    clean = str(value or "").strip()
    return clean or None


def account_access_active(access_valid_until: str | None, *, now: str | None = None) -> bool:
    until = _parse_until(access_valid_until)
    if until is None:
        return True
    reference = now or utc_now()
    return until >= reference


class UserAuthService:
    """Manage ERP users in the installation catalog."""

    def __init__(self, databases: DatabaseManager) -> None:
        self.databases = databases

    def user_count(self) -> int:
        with self.databases.connect(self.databases.catalog_path) as connection:
            row = connection.execute("SELECT COUNT(*) AS c FROM app_user").fetchone()
        return int(row["c"]) if row else 0

    def login_required(self) -> bool:
        return self.user_count() > 0

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        clean = username.strip()
        if not clean or not password:
            raise ValidationError("Username and password are required")
        with self.databases.connect(self.databases.catalog_path) as connection:
            row = connection.execute(
                """
                SELECT user_id, username, password_hash, display_name, role,
                    can_view_kachi, is_active, use_custom_menu, access_valid_until
                FROM app_user
                WHERE username = ? COLLATE NOCASE
                """,
                (clean,),
            ).fetchone()
        if row is None or int(row["is_active"]) != 1:
            raise ValidationError("Invalid username or password")
        if not account_access_active(str(row["access_valid_until"] or "")):
            raise ValidationError("User access has expired — contact the owner")
        if not verify_password(password, str(row["password_hash"])):
            raise ValidationError("Invalid username or password")

        token = secrets.token_urlsafe(32)
        session_id = str(uuid.uuid4())
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
        user = self._user_row_to_dict(row)
        user["permissions"] = self.list_permissions(str(row["user_id"]))
        return {"token": token, "expires_at": expires, "user": user}

    def resolve_token(self, token: str) -> dict[str, Any]:
        if not token.strip():
            raise ValidationError("Missing session token")
        token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        with self.databases.connect(self.databases.catalog_path) as connection:
            row = connection.execute(
                """
                SELECT
                    s.session_id, s.expires_at,
                    u.user_id, u.username, u.display_name, u.role,
                    u.can_view_kachi, u.is_active, u.use_custom_menu, u.access_valid_until
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
        if not account_access_active(str(row["access_valid_until"] or "")):
            raise ValidationError("User access has expired — contact the owner")
        user = self._user_row_to_dict(row)
        user["permissions"] = self.list_permissions(str(row["user_id"]))
        return user

    def logout(self, token: str) -> None:
        if not token.strip():
            return
        token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        with self.databases.connect(self.databases.catalog_path) as connection:
            connection.execute("DELETE FROM app_session WHERE token_hash = ?", (token_hash,))

    def list_users(self) -> list[dict[str, Any]]:
        with self.databases.connect(self.databases.catalog_path) as connection:
            rows = connection.execute(
                """
                SELECT user_id, username, display_name, role, can_view_kachi, is_active,
                    use_custom_menu, access_valid_until, created_at, updated_at
                FROM app_user
                ORDER BY username COLLATE NOCASE
                """
            ).fetchall()
        return [self._user_row_to_dict(row) for row in rows]

    def save_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        username = str(payload.get("username", "")).strip()
        display_name = str(payload.get("display_name", "")).strip() or username
        role = str(payload.get("role", "clerk")).strip().lower()
        if role not in VALID_ROLES:
            raise ValidationError("Invalid role")
        user_id = str(payload.get("user_id") or uuid.uuid4())
        can_view = payload.get("can_view_kachi")
        can_view_kachi = default_can_view_kachi(role) if can_view is None else bool(can_view)
        is_active = 1 if payload.get("is_active", True) else 0
        use_custom_menu = 1 if payload.get("use_custom_menu") else 0
        access_valid_until = _parse_until(str(payload.get("access_valid_until") or ""))
        access_days = payload.get("access_days")
        if access_days is not None and str(access_days).strip().isdigit():
            days = int(str(access_days).strip())
            if days > 0:
                access_valid_until = (
                    datetime.now(UTC) + timedelta(days=days)
                ).isoformat(timespec="seconds")
        password = str(payload.get("password", "")).strip()
        timestamp = utc_now()
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
                    connection.execute(
                        """
                        UPDATE app_user SET
                            username = ?, display_name = ?, role = ?,
                            can_view_kachi = ?, is_active = ?, use_custom_menu = ?,
                            access_valid_until = ?, password_hash = ?, updated_at = ?
                        WHERE user_id = ?
                        """,
                        (
                            username,
                            display_name,
                            role,
                            int(can_view_kachi),
                            is_active,
                            use_custom_menu,
                            access_valid_until,
                            hash_password(password),
                            timestamp,
                            user_id,
                        ),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE app_user SET
                            username = ?, display_name = ?, role = ?,
                            can_view_kachi = ?, is_active = ?, use_custom_menu = ?,
                            access_valid_until = ?, updated_at = ?
                        WHERE user_id = ?
                        """,
                        (
                            username,
                            display_name,
                            role,
                            int(can_view_kachi),
                            is_active,
                            use_custom_menu,
                            access_valid_until,
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
                        can_view_kachi, is_active, use_custom_menu, access_valid_until,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        hash_password(password),
                        display_name,
                        role,
                        int(can_view_kachi),
                        is_active,
                        use_custom_menu,
                        access_valid_until,
                        timestamp,
                        timestamp,
                    ),
                )
        return self.get_user(user_id)

    def delete_user(self, user_id: str) -> None:
        clean = str(user_id).strip()
        with self.databases.connect(self.databases.catalog_path) as connection:
            row = connection.execute(
                "SELECT role FROM app_user WHERE user_id = ?", (clean,)
            ).fetchone()
            if row is None:
                raise ValidationError("User not found")
            if str(row["role"]) == "admin":
                admins = connection.execute(
                    "SELECT COUNT(*) AS c FROM app_user WHERE role = 'admin' AND is_active = 1"
                ).fetchone()
                if admins and int(admins["c"]) <= 1:
                    raise ValidationError("Cannot delete the last active administrator")
            connection.execute("DELETE FROM app_user_permission WHERE user_id = ?", (clean,))
            connection.execute("DELETE FROM app_session WHERE user_id = ?", (clean,))
            connection.execute("DELETE FROM app_user WHERE user_id = ?", (clean,))

    def get_user(self, user_id: str) -> dict[str, Any]:
        with self.databases.connect(self.databases.catalog_path) as connection:
            row = connection.execute(
                """
                SELECT user_id, username, display_name, role, can_view_kachi, is_active,
                    use_custom_menu, access_valid_until, created_at, updated_at
                FROM app_user WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            raise ValidationError("User not found")
        data = self._user_row_to_dict(row)
        data["permissions"] = self.list_permissions(user_id)
        return data

    def list_permissions(self, user_id: str) -> dict[str, str]:
        now = utc_now()
        with self.databases.connect(self.databases.catalog_path) as connection:
            rows = connection.execute(
                """
                SELECT permission_key, access_level, valid_until
                FROM app_user_permission
                WHERE user_id = ? AND enabled = 1
                """,
                (user_id,),
            ).fetchall()
        active: dict[str, str] = {}
        for row in rows:
            until = _parse_until(str(row["valid_until"] or ""))
            if until is not None and until < now:
                continue
            level = str(row["access_level"]).lower()
            if level not in {"read", "write"}:
                continue
            active[str(row["permission_key"])] = level
        return active

    def save_permissions(self, user_id: str, grants: list[dict[str, Any]]) -> dict[str, str]:
        clean_id = str(user_id).strip()
        if not connection_row_exists(self.databases, clean_id):
            raise ValidationError("User not found")
        with self.databases.connect(self.databases.catalog_path) as connection:
            connection.execute(
                "DELETE FROM app_user_permission WHERE user_id = ?", (clean_id,)
            )
            for grant in grants:
                key = str(grant.get("permission_key") or "").strip()
                if not key:
                    continue
                enabled = 1 if grant.get("enabled") else 0
                level = str(grant.get("access_level") or "read").lower()
                if level not in {"read", "write"}:
                    level = "read"
                valid_until = _parse_until(str(grant.get("valid_until") or ""))
                days = grant.get("valid_days")
                if enabled and days is not None and str(days).strip().isdigit():
                    day_count = int(str(days).strip())
                    if day_count > 0:
                        valid_until = (
                            datetime.now(UTC) + timedelta(days=day_count)
                        ).isoformat(timespec="seconds")
                connection.execute(
                    """
                    INSERT INTO app_user_permission(
                        user_id, permission_key, access_level, enabled, valid_until
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (clean_id, key, level, enabled, valid_until),
                )
        return self.list_permissions(clean_id)

    @staticmethod
    def _user_row_to_dict(row: Any) -> dict[str, Any]:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        use_custom = int(row["use_custom_menu"] or 0) if "use_custom_menu" in keys else 0
        access_until = str(row["access_valid_until"] or "") if "access_valid_until" in keys else ""
        return {
            "user_id": str(row["user_id"]),
            "username": str(row["username"]),
            "display_name": str(row["display_name"]),
            "role": str(row["role"]),
            "can_view_kachi": bool(int(row["can_view_kachi"])),
            "is_active": bool(int(row["is_active"])),
            "use_custom_menu": bool(use_custom),
            "access_valid_until": access_until,
        }


def connection_row_exists(databases: DatabaseManager, user_id: str) -> bool:
    with databases.connect(databases.catalog_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM app_user WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row is not None
