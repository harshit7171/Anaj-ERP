"""Request-scoped LAN access policy for multi-user office server."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from .errors import ValidationError


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    """Role and flags applied to one authenticated LAN session."""

    user_id: str
    username: str
    role: str
    can_view_kachi: bool

    @classmethod
    def local_desktop(cls) -> AccessPolicy:
        """Full access for standalone pywebview sessions."""
        return cls(
            user_id="local",
            username="local",
            role="admin",
            can_view_kachi=True,
        )

    def allows_read(self) -> bool:
        return self.role in {"admin", "munim", "clerk", "operator", "readonly"}

    def allows_write(self) -> bool:
        return self.role in {"admin", "munim", "operator"}

    def allows_user_admin(self) -> bool:
        return self.role == "admin"

    def assert_read(self) -> None:
        if not self.allows_read():
            raise ValidationError("Read access denied for this user")

    def assert_write(self) -> None:
        if not self.allows_write():
            raise ValidationError("Write access denied for this user")

    def assert_user_admin(self) -> None:
        if not self.allows_user_admin():
            raise ValidationError("Administrator access required")


_current_access: ContextVar[AccessPolicy | None] = ContextVar(
    "anaj_current_access",
    default=None,
)


def set_current_access(policy: AccessPolicy | None) -> None:
    """Bind access policy for the active server request."""
    _current_access.set(policy)


def current_access() -> AccessPolicy:
    """Return active access policy (local desktop when unset)."""
    policy = _current_access.get()
    if policy is None:
        return AccessPolicy.local_desktop()
    return policy


def is_lan_session() -> bool:
    """True when handling an authenticated LAN RPC (not local desktop)."""
    policy = _current_access.get()
    return policy is not None and policy.user_id != "local"
