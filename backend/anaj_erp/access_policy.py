"""Local desktop access policy (standalone single-PC)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from .errors import ValidationError
from .user_permission_catalog import normalize_permission_key


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    """Role and flags for the active desktop session."""

    user_id: str
    username: str
    role: str
    can_view_kachi: bool
    use_custom_menu: bool = False
    permissions: dict[str, str] = field(default_factory=dict)
    access_valid_until: str = ""

    @classmethod
    def local_desktop(cls) -> AccessPolicy:
        return cls(
            user_id="local",
            username="local",
            role="admin",
            can_view_kachi=True,
            use_custom_menu=False,
        )

    @classmethod
    def from_session(cls, session: dict[str, Any]) -> AccessPolicy:
        return cls(
            user_id=str(session.get("user_id") or ""),
            username=str(session.get("username") or ""),
            role=str(session.get("role") or "readonly"),
            can_view_kachi=bool(session.get("can_view_kachi")),
            use_custom_menu=bool(session.get("use_custom_menu")),
            permissions=dict(session.get("permissions") or {}),
            access_valid_until=str(session.get("access_valid_until") or ""),
        )

    def is_admin(self) -> bool:
        return self.role == "admin"

    def allows_window(self, window_title: str) -> bool:
        if self.is_admin() or not self.use_custom_menu:
            return True
        key = normalize_permission_key(window_title)
        return key in self.permissions

    def window_access_level(self, window_title: str) -> str:
        if self.is_admin() or not self.use_custom_menu:
            return "write" if self.allows_write() else "read"
        key = normalize_permission_key(window_title)
        return self.permissions.get(key, "none")

    def allows_read(self) -> bool:
        return self.role in {"admin", "munim", "clerk", "operator", "readonly"}

    def allows_write(self) -> bool:
        if self.role in {"clerk", "readonly"}:
            return False
        if self.is_admin():
            return True
        if not self.use_custom_menu:
            return self.role in {"admin", "munim", "operator"}
        return any(level == "write" for level in self.permissions.values())

    def allows_write_window(self, window_title: str) -> bool:
        if not self.allows_write() and self.role not in {"admin", "munim", "operator"}:
            return False
        if self.is_admin() or not self.use_custom_menu:
            return self.allows_write()
        return self.window_access_level(window_title) == "write"

    def allows_user_admin(self) -> bool:
        return self.is_admin()

    def assert_read(self) -> None:
        if not self.allows_read():
            raise ValidationError("Read access denied for this user")

    def assert_write(self) -> None:
        if not self.allows_write():
            raise ValidationError("Write access denied for this user")

    def assert_user_admin(self) -> None:
        if not self.allows_user_admin():
            raise ValidationError("Administrator access required")

    def assert_window(self, window_title: str) -> None:
        if not self.allows_window(window_title):
            raise ValidationError("This screen is not enabled for your user")


_current_access: ContextVar[AccessPolicy | None] = ContextVar(
    "anaj_current_access",
    default=None,
)


def current_access() -> AccessPolicy:
    policy = _current_access.get()
    if policy is None:
        return AccessPolicy.local_desktop()
    return policy


def bind_access(policy: AccessPolicy) -> None:
    _current_access.set(policy)


def clear_access_binding() -> None:
    _current_access.set(None)
