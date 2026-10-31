"""FastAPI office LAN server — shared SQLite on one Windows PC."""

from __future__ import annotations

import inspect
import logging
import os
import threading
from pathlib import Path
from typing import Any

from .api import ApplicationApi
from .database import DatabaseManager
from .errors import ValidationError
from .lan_auth import UserService
from .lan_session import AccessPolicy
from .lan_session import set_current_access
from . import lan_runtime
from .lan_discovery import office_beacon_payload
from .licensing import LicenseService

logger = logging.getLogger(__name__)

_rpc_lock = threading.RLock()

READ_METHODS = frozenset(
    {
        "health",
        "license_status",
        "list_companies",
        "list_financial_years",
        "context_payload",
        "compliance_status",
        "dashboard_summary",
        "farmer_credit_dashboard",
        "list_charge_rules",
        "list_agricultural_groups",
        "search_master",
        "trial_balance",
        "stock_balance",
        "day_book",
        "account_ledger",
        "cash_book",
        "tax_register",
        "financial_statements",
        "document_register",
        "calculate_interest",
        "run_report",
        "find_accounts",
        "get_company_settings",
        "list_prefix_settings",
        "list_lan_users",
        "run_diagnostics",
        "print_cash_book_register",
        "print_day_book_register",
        "print_voucher",
        "whatsapp_for_document",
        "whatsapp_payment_reminder",
        "open_whatsapp_url",
        "generate_reminder_letters",
        "import_bank_statement",
        "list_document_attachments",
        "blended_average_cost",
        "lookup_gstin",
        "get_party_master",
        "get_account_master",
        "list_narrations",
        "get_narration",
        "list_cities",
        "get_city",
        "list_transports",
        "get_transport",
        "list_banks",
        "get_bank",
        "list_ifsc_codes",
        "get_ifsc_code",
        "list_items",
        "get_item",
        "list_stock_entries",
        "get_stock_entry_master",
        "list_trading_accounts",
        "get_trading_account",
        "list_expense_masters",
        "get_expense_master",
        "list_cheque_print_settings",
        "get_cheque_print_setting",
        "list_i_form_expense_defines",
        "get_i_form_expense_define",
        "document_lock_status",
        "list_document_locks",
        "fetch_mandi_bhav",
        "auction_board_snapshot",
        "start_cloud_oauth",
        "export_table",
        "get_print_design",
        "print_mandi_bill",
        "print_party_ledger",
    }
)

WRITE_METHODS = frozenset(
    {
        "select_context",
        "create_company",
        "create_financial_year",
        "set_year_lock",
        "create_account",
        "create_party",
        "create_commodity",
        "create_charge_rule",
        "revise_charge_rule",
        "update_party",
        "post_voucher",
        "post_document",
        "calculate_document",
        "save_city",
        "delete_city",
        "save_transport",
        "delete_transport",
        "save_trading_account",
        "delete_trading_account",
        "save_narration",
        "delete_narration",
        "delete_account_master",
        "save_bank",
        "delete_bank",
        "save_ifsc_code",
        "delete_ifsc_code",
        "save_expense_master",
        "delete_expense_master",
        "save_cheque_print_setting",
        "delete_cheque_print_setting",
        "save_i_form_expense_define",
        "delete_i_form_expense_define",
        "save_item_master",
        "delete_item",
        "save_account_master",
        "save_opening_stock",
        "save_stock_entry_master",
        "delete_stock_entry_master",
        "save_stock_adjustment",
        "save_company_settings",
        "save_prefix_setting",
        "create_backup",
        "restore_new_company",
        "import_master_csv",
        "reconcile_company",
        "install_license",
        "save_lan_user",
        "set_company_profile",
        "merge_parties",
        "attach_document_file",
        "print_cover_address",
        "acquire_document_lock",
        "release_document_lock",
        "upsert_auction_lot",
        "place_auction_bid",
        "close_auction_lot",
        "poll_cloud_oauth",
        "run_encrypted_cloud_backup",
        "save_print_design",
    }
)

ADMIN_METHODS = frozenset({"list_lan_users", "save_lan_user", "set_company_profile"})

try:
    from pydantic import BaseModel

    class LoginBody(BaseModel):
        username: str
        password: str

    class RpcBody(BaseModel):
        method: str
        params: dict[str, Any] | None = None

except ImportError:
    LoginBody = None  # type: ignore[misc, assignment]
    RpcBody = None  # type: ignore[misc, assignment]


def _resource_path(relative_path: str) -> Path:
    return Path(__file__).resolve().parents[2] / relative_path


def create_app(
    data_dir: Path | None = None,
    *,
    bootstrap_password: str | None = None,
    development_mode: bool = False,
) -> Any:
    """Build the FastAPI application (import deferred for optional dependency)."""
    try:
        from fastapi import Depends
        from fastapi import FastAPI
        from fastapi import Header
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as exc:
        raise ImportError(
            "Install server extras: pip install -e \".[server]\""
        ) from exc

    databases = DatabaseManager(data_dir)
    databases.initialize()
    license_service: LicenseService | None
    if development_mode:
        license_service = None
    else:
        public_key = _resource_path("resources/license_public_key.pem")
        license_service = LicenseService(databases, public_key.read_bytes())
    api = ApplicationApi(databases, license_service)
    users = UserService(databases)
    users.ensure_schema()
    password = bootstrap_password or os.environ.get("ANAJ_ERP_ADMIN_PASSWORD", "")
    if password:
        created = users.bootstrap_admin_if_empty(password)
        if created:
            logger.warning(
                "Bootstrap admin user created",
                extra={"username": created["username"]},
            )

    if LoginBody is None or RpcBody is None:
        raise ImportError("Install server extras: pip install -e \".[server]\"")

    app = FastAPI(title="Anaj ERP Office Server", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    http_port = int(os.environ.get("ANAJ_ERP_PORT", "8765"))
    office_name = os.environ.get("ANAJ_ERP_OFFICE_NAME", "Anaj ERP Office")

    @app.on_event("startup")
    async def _startup_live_hub() -> None:
        import asyncio

        lan_runtime.live_hub.attach_loop(asyncio.get_running_loop())
        lan_runtime.auction_board.seed_demo_lots()
        from .lan_discovery import DiscoveryBroadcaster

        broadcaster = DiscoveryBroadcaster(
            http_port=http_port,
            office_name=office_name,
        )
        lan_runtime.discovery_broadcaster = broadcaster
        broadcaster.start()
        logger.info("LAN discovery beacon started on UDP %s", 8766)

    @app.on_event("shutdown")
    def _shutdown_beacon() -> None:
        if lan_runtime.discovery_broadcaster is not None:
            lan_runtime.discovery_broadcaster.stop()

    def resolve_policy(authorization: str | None = Header(default=None)) -> AccessPolicy:
        from fastapi import HTTPException

        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Authorization required")
        token = authorization.split(" ", 1)[1].strip()
        try:
            profile = users.resolve_token(token)
        except ValidationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return AccessPolicy(
            user_id=str(profile["user_id"]),
            username=str(profile["username"]),
            role=str(profile["role"]),
            can_view_kachi=bool(profile["can_view_kachi"]),
        )

    @app.get("/health")
    def health() -> dict[str, object]:
        payload = api.health()
        payload["server_mode"] = True
        payload["ws_path"] = "/ws/live"
        return payload

    @app.get("/api/v1/office-beacon")
    def office_beacon() -> dict[str, object]:
        return office_beacon_payload(office_name, http_port)

    @app.post("/auth/login")
    def login(credentials: LoginBody) -> dict[str, object]:
        try:
            session = users.authenticate(credentials.username, credentials.password)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, **session}

    @app.post("/api/v1/rpc")
    def rpc(
        call: RpcBody,
        policy: AccessPolicy = Depends(resolve_policy),
    ) -> dict[str, object]:
        from fastapi import HTTPException

        method = call.method.strip()
        if method not in READ_METHODS and method not in WRITE_METHODS:
            raise HTTPException(status_code=403, detail=f"Method not allowed: {method}")
        try:
            if method in ADMIN_METHODS:
                policy.assert_user_admin()
            elif method in WRITE_METHODS:
                policy.assert_write()
            else:
                policy.assert_read()
        except ValidationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        fn = getattr(api, method, None)
        if fn is None or not callable(fn):
            raise HTTPException(status_code=404, detail=f"Unknown method: {method}")

        params = dict(call.params or {})
        if method in {"post_document", "post_voucher"}:
            nested = params.get("payload")
            lock_key = str(params.get("lock_resource_key") or "").strip()
            if not lock_key and isinstance(nested, dict):
                lock_key = str(nested.get("lock_resource_key") or "").strip()
            if lock_key:
                status = lan_runtime.lock_coordinator.status(lock_key)
                if status.get("locked") and status.get("holder") != policy.user_id:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Locked by {status.get('holder_label', 'another user')}",
                    )
        with _rpc_lock:
            set_current_access(policy)
            try:
                signature = inspect.signature(fn)
                bound = signature.bind_partial(**params)
                bound.apply_defaults()
                result = fn(*bound.args, **bound.kwargs)
            finally:
                set_current_access(None)
        if not isinstance(result, dict):
            return {"ok": True, "result": result}
        return result

    @app.websocket("/ws/live")
    async def live_socket(websocket: Any) -> None:
        from fastapi import WebSocketDisconnect

        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4401)
            return
        try:
            users.resolve_token(str(token))
        except ValidationError:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        await lan_runtime.live_hub.register(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await lan_runtime.live_hub.unregister(websocket)

    return app
