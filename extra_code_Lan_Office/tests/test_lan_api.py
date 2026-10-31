"""Phase 8 office LAN server auth and RPC."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from anaj_erp.database import DatabaseManager
from anaj_erp.lan_server import create_app


def test_lan_login_and_list_companies(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "office")
    databases.initialize()
    app = create_app(
        tmp_path / "office",
        bootstrap_password="PilotAdmin123!",
        development_mode=True,
    )
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["server_mode"] is True

    bad = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 200
    assert bad.json()["ok"] is False

    login = client.post(
        "/auth/login",
        json={"username": "admin", "password": "PilotAdmin123!"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["ok"] is True
    token = str(body["token"])
    headers = {"Authorization": f"Bearer {token}"}

    companies = client.post(
        "/api/v1/rpc",
        json={"method": "list_companies", "params": {}},
        headers=headers,
    )
    assert companies.status_code == 200
    assert companies.json()["ok"] is True


def test_clerk_cannot_create_company(tmp_path: Path) -> None:
    app = create_app(
        tmp_path / "office2",
        bootstrap_password="PilotAdmin123!",
        development_mode=True,
    )
    client = TestClient(app)
    admin = client.post(
        "/auth/login",
        json={"username": "admin", "password": "PilotAdmin123!"},
    ).json()
    token = admin["token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/v1/rpc",
        json={
            "method": "save_lan_user",
            "params": {
                "payload": {
                    "username": "clerk1",
                    "display_name": "Clerk",
                    "password": "ClerkPass123!",
                    "role": "clerk",
                    "can_view_kachi": False,
                },
            },
        },
        headers=headers,
    )
    clerk_login = client.post(
        "/auth/login",
        json={"username": "clerk1", "password": "ClerkPass123!"},
    ).json()
    clerk_headers = {"Authorization": f"Bearer {clerk_login['token']}"}
    denied = client.post(
        "/api/v1/rpc",
        json={
            "method": "create_company",
            "params": {"name": "Denied Co", "start_year": 2026},
        },
        headers=clerk_headers,
    )
    assert denied.status_code == 403
