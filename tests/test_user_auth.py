"""Standalone user login and menu permissions."""

from __future__ import annotations

from pathlib import Path

from anaj_erp.access_policy import AccessPolicy
from anaj_erp.api import ApplicationApi
from anaj_erp.database import DatabaseManager


def test_first_user_and_login(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "users")
    databases.initialize()
    api = ApplicationApi(databases)

    status = api.user_login_status()
    assert status["ok"] is True
    assert status["login_required"] is False

    saved = api.save_lan_user(
        {
            "username": "owner",
            "password": "secret123",
            "role": "admin",
            "display_name": "Owner",
        }
    )
    assert saved["ok"] is True

    owner_login = api.user_login("owner", "secret123")
    assert owner_login["ok"] is True

    munim = api.save_lan_user(
        {
            "username": "munim1",
            "password": "munim123",
            "role": "munim",
            "use_custom_menu": True,
            "permissions": [
                {
                    "permission_key": "Ledger",
                    "enabled": True,
                    "access_level": "read",
                    "valid_days": 3,
                }
            ],
        }
    )
    assert munim["ok"] is True

    assert api.user_login_status()["login_required"] is True
    api.user_logout()

    bad = api.user_login("munim1", "wrong")
    assert bad["ok"] is False

    good = api.user_login("munim1", "munim123")
    assert good["ok"] is True
    session = good["session"]
    assert session["username"] == "munim1"
    assert session["permissions"].get("Ledger") == "read"

    policy = AccessPolicy.from_session(session)
    assert policy.allows_window("Ledger")
    assert not policy.allows_write_window("Ledger")
    assert not policy.allows_window("Account Master Add")
