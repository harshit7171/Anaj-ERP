"""FastAPI fleet renewal portal for vendor operations (Point 35)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .fleet_licensing import FleetRegistry


def create_fleet_app(registry: FleetRegistry | None = None) -> Any:
    try:
        from fastapi import Depends
        from fastapi import FastAPI
        from fastapi import Header
        from fastapi import HTTPException
        from pydantic import BaseModel
    except ImportError as exc:
        raise ImportError('Install server extras: pip install -e ".[server]"') from exc

    db_path = Path(os.environ.get("ANAJ_FLEET_DB", "fleet/fleet.db"))
    fleet = registry or FleetRegistry(db_path)
    admin_token = os.environ.get("ANAJ_FLEET_ADMIN_TOKEN", "").strip()
    private_key_path = os.environ.get("ANAJ_FLEET_PRIVATE_KEY_PEM", "").strip()

    class HeartbeatBody(BaseModel):
        installation_id: str
        customer_name: str = ""
        license_valid_until: str = ""
        app_version: str = ""

    class IssueBody(BaseModel):
        installation_id: str
        customer_name: str
        valid_from: str
        valid_until: str
        features: list[str] | None = None

    class RevokeBody(BaseModel):
        installation_id: str
        revoked: bool = True

    app = FastAPI(title="Anaj ERP Fleet Licensing", version="0.1.0")

    def require_admin(authorization: str | None = Header(default=None)) -> None:
        if not admin_token:
            raise HTTPException(status_code=503, detail="ANAJ_FLEET_ADMIN_TOKEN not configured")
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Authorization required")
        token = authorization.split(" ", 1)[1].strip()
        if token != admin_token:
            raise HTTPException(status_code=403, detail="Invalid admin token")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "fleet-licensing"}

    @app.post("/api/v1/heartbeat")
    def heartbeat(body: HeartbeatBody) -> dict[str, Any]:
        try:
            return fleet.heartbeat(
                body.installation_id,
                body.customer_name,
                license_valid_until=body.license_valid_until,
                app_version=body.app_version,
            )
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}

    @app.get("/api/v1/machines")
    def machines(_: None = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, "machines": fleet.list_machines()}

    @app.post("/api/v1/issue-license")
    def issue_license(body: IssueBody, _: None = Depends(require_admin)) -> dict[str, Any]:
        if not private_key_path or not Path(private_key_path).is_file():
            raise HTTPException(status_code=503, detail="ANAJ_FLEET_PRIVATE_KEY_PEM missing")
        key_bytes = Path(private_key_path).read_bytes()
        token = fleet.issue_license_token(
            key_bytes,
            installation_id=body.installation_id,
            customer_name=body.customer_name,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            features=body.features,
        )
        return {"ok": True, "license_token": token}

    @app.post("/api/v1/revoke")
    def revoke(body: RevokeBody, _: None = Depends(require_admin)) -> dict[str, Any]:
        return fleet.revoke(body.installation_id, revoked=body.revoked)

    return app
