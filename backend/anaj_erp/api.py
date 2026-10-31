"""Validated pywebview API exposed to the React desktop interface."""

from __future__ import annotations

import logging
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .accounting import AccountingService
from .backup import BackupService
from .database import DatabaseManager
from .documents import DocumentService
from .errors import AnajError
from .errors import ValidationError
from .licensing import LicenseService
from .maintenance import MaintenanceService
from .masters import MasterService
from .printing import InvoicePrinter
from .register_pdf import RegisterPdfPrinter
from .credit import CreditLimitService
from .access_policy import AccessPolicy
from .access_policy import bind_access
from .access_policy import clear_access_binding
from .access_policy import current_access
from .user_auth import UserAuthService
from .user_permission_catalog import list_permission_catalog
from .report_catalog import ReportCatalog
from .reports import ReportService
from .kachi_purchase import KachiPurchaseService
from .gst_purchase_entry import GstPurchaseEntryService
from .invoice_entry import InvoiceEntryService
from .gst_debit_note_entry import GstDebitNoteEntryService
from .gst_credit_note_entry import GstCreditNoteEntryService
from .gst_expense_voucher_entry import GstExpenseVoucherEntryService
from .accounting_note_entry import AccountingNoteEntryService
from .voucher_entry import VoucherEntryService
from .tds_challan_entry import TdsChallanEntryService
from .bank_reconciliation import BankReconciliationService
from .search_screens import SearchScreensService
from .gst_reports import GstReportsService
from .mandi_purchase_entry import MandiPurchaseEntryService
from .lifting_entry import LiftingEntryService
from .tools import ToolsService
from .modern_features import ModernFeaturesService
from .agmarknet_client import fetch_mandi_bhav
from .cloud_backup import encrypt_file
from .cloud_backup import poll_oauth_device_flow
from .cloud_backup import run_exit_cloud_backup
from .cloud_backup import start_oauth_device_flow
from .cloud_backup import upload_encrypted_backup
from .gst_lookup import lookup_gstin_online
from .google_drive_backup import apply_google_drive_backup
from . import standalone_runtime

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ActiveContext:
    """Currently selected company and financial year."""

    company_id: str
    financial_year_id: str
    financial_year_label: str


class ApplicationApi:
    """Thread-safe bridge used by pywebview JavaScript calls."""

    def __init__(
        self,
        databases: DatabaseManager,
        license_service: LicenseService | None = None,
    ) -> None:
        """Store initialized database manager and empty active context."""
        self.databases = databases
        self.license_service = license_service
        self._context: ActiveContext | None = None
        self._lock = threading.RLock()
        self._gstr2b_portal_records: list[Any] | None = None
        self._session_token: str | None = None
        self._users = UserAuthService(databases)

    def health(self) -> dict[str, object]:
        """Return local runtime health information."""
        return {
            "ok": True,
            "installation_id": self.databases.installation_id(),
            "offline": True,
            "license": self.license_status(),
        }

    def license_status(self) -> dict[str, object]:
        """Return annual entitlement state for the startup screen."""
        if self.license_service is None:
            return {"ok": True, "valid": True, "development_mode": True}
        try:
            return {"ok": True, **self.license_service.status()}
        except AnajError as exc:
            return self._error(exc)

    def install_license(self, token: str) -> dict[str, object]:
        """Install a vendor-signed key entered through AnyDesk support."""
        if self.license_service is None:
            return self._error(ValidationError("License verification is not configured"))
        try:
            return self._result(license=self.license_service.install(token))
        except (AnajError, ValueError, TypeError, KeyError) as exc:
            return self._error(exc)

    def list_companies(self) -> dict[str, object]:
        """Return companies for the startup selector."""
        def action() -> dict[str, object]:
            companies = self.databases.list_companies()
            return {"companies": companies}

        return self._call(action)

    def create_company(
        self,
        name: str,
        start_year: int,
        company_profile: str = "standard",
    ) -> dict[str, object]:
        """Create a company after boundary validation."""
        def action() -> dict[str, object]:
            company = self.databases.create_company(
                name,
                int(start_year),
                company_profile=str(company_profile),
            )
            logger.info("Company created", extra={"company_id": company["company_id"]})
            return {"company": company}

        return self._write_call(action)

    def list_financial_years(self, company_id: str) -> dict[str, object]:
        """Return selectable years for one company."""
        try:
            if self.license_service is not None:
                self.license_service.assert_session_safe()
            years = self.databases.list_financial_years(company_id)
            return self._result(financial_years=years)
        except AnajError as exc:
            return self._error(exc)

    def select_context(
        self,
        company_id: str,
        financial_year_id: str,
    ) -> dict[str, object]:
        """Select a valid company/year pair for all later operations."""
        try:
            if self.license_service is not None:
                self.license_service.assert_can_open()
            years = self.databases.list_financial_years(company_id)
            selected = next(
                (
                    year
                    for year in years
                    if year["financial_year_id"] == financial_year_id
                ),
                None,
            )
            if selected is None:
                raise ValidationError("Financial year does not belong to this company")
            with self._lock:
                self._context = ActiveContext(
                    company_id=company_id,
                    financial_year_id=financial_year_id,
                    financial_year_label=str(selected["label"]),
                )
            return self._result(context=self.context_payload())
        except AnajError as exc:
            return self._error(exc)

    def context_payload(self) -> dict[str, str] | None:
        """Return a JSON-safe active context snapshot."""
        with self._lock:
            if self._context is None:
                return None
            return {
                "company_id": self._context.company_id,
                "financial_year_id": self._context.financial_year_id,
                "financial_year_label": self._context.financial_year_label,
            }

    def create_financial_year(self, start_year: int) -> dict[str, object]:
        """Create a financial year in the active company."""
        return self._write_call(
            lambda: {
                "financial_year": self._accounting().add_financial_year(int(start_year))
            }
        )

    def set_year_lock(self, locked: bool, reason: str) -> dict[str, object]:
        """Lock or reopen the selected year with an audit reason."""
        def action() -> dict[str, object]:
            context = self._require_context()
            self._accounting().set_year_lock(
                context.financial_year_id,
                bool(locked),
                reason,
            )
            return {"locked": bool(locked)}

        return self._write_call(action)

    def create_account(self, name: str, account_type: str) -> dict[str, object]:
        """Create a ledger account in the active company."""
        return self._write_call(
            lambda: {
                "account": self._accounting().create_account(name, account_type)
            }
        )

    def create_party(self, payload: dict[str, Any]) -> dict[str, object]:
        """Create a validated party master."""
        return self._write_call(
            lambda: {
                "party": self._accounting().create_party(
                    str(payload.get("name", "")),
                    str(payload.get("party_type", "")),
                    gstin=str(payload.get("gstin", "")),
                    pan=str(payload.get("pan", "")),
                    address=str(payload.get("address", "")),
                    city=str(payload.get("city", "")),
                    phone=str(payload.get("phone", "")),
                    related_name=str(payload.get("related_name", "")),
                    father_name=str(payload.get("father_name", "")),
                    agricultural_group=str(payload.get("agricultural_group", "")),
                    village_name=str(payload.get("village_name", "")),
                    credit_limit_paise=int(payload.get("credit_limit_paise", 0)),
                    account_id=payload.get("account_id"),
                )
            }
        )

    def update_party(self, party_id: str, payload: dict[str, Any]) -> dict[str, object]:
        """Update an existing party/farmer master."""
        return self._write_call(
            lambda: {
                "party": self._accounting().update_party(
                    party_id,
                    name=payload.get("name"),
                    father_name=payload.get("father_name"),
                    agricultural_group=payload.get("agricultural_group"),
                    village_name=payload.get("village_name"),
                    credit_limit_paise=(
                        int(payload["credit_limit_paise"])
                        if "credit_limit_paise" in payload
                        else None
                    ),
                    gstin=payload.get("gstin"),
                    pan=payload.get("pan"),
                    address=payload.get("address"),
                    city=payload.get("city"),
                    phone=payload.get("phone"),
                    account_id=payload.get("account_id"),
                )
            }
        )

    def list_agricultural_groups(self) -> dict[str, object]:
        """Return configured agricultural groups for farmer masters."""
        return self._call(
            lambda: {"groups": self._accounting().list_agricultural_groups()}
        )

    def create_commodity(self, payload: dict[str, Any]) -> dict[str, object]:
        """Create a validated commodity master."""
        return self._write_call(
            lambda: {
                "commodity": self._accounting().create_commodity(
                    str(payload.get("name", "")),
                    variety=str(payload.get("variety", "")),
                    hsn_code=str(payload.get("hsn_code", "")),
                    quantity_scale=int(payload.get("quantity_scale", 3)),
                    standard_bag_weight_scaled=payload.get(
                        "standard_bag_weight_scaled"
                    ),
                )
            }
        )

    def create_charge_rule(self, payload: dict[str, Any]) -> dict[str, object]:
        """Create an effective-dated Haryana calculation rule."""
        return self._write_call(
            lambda: {
                "charge_rule": self._accounting().create_charge_rule(**payload)
            }
        )

    def list_charge_rules(
        self,
        transaction_type: str = "",
        as_of_date: str = "",
    ) -> dict[str, object]:
        """List effective charge rules for administration."""
        return self._call(
            lambda: {
                "charge_rules": self._accounting().list_charge_rules(
                    transaction_type=transaction_type or None,
                    as_of_date=as_of_date or None,
                )
            }
        )

    def revise_charge_rule(
        self,
        charge_rule_id: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        """Create a successor charge rule without rewriting historical snapshots."""
        return self._write_call(
            lambda: {
                "charge_rule": self._accounting().revise_charge_rule(
                    charge_rule_id,
                    rate_decimal=payload.get("rate_decimal"),
                    label=payload.get("label"),
                    effective_from=payload.get("effective_from"),
                    effective_to=payload.get("effective_to"),
                    priority=payload.get("priority"),
                )
            }
        )

    def search_master(
        self,
        entity_type: str,
        query: str,
        limit: int = 20,
    ) -> dict[str, object]:
        """Search a master for keyboard autocomplete."""
        return self._call(
            lambda: {
                "items": self._accounting().search(entity_type, query, int(limit))
            }
        )

    def post_voucher(self, payload: dict[str, Any]) -> dict[str, object]:
        """Post a balanced journal/cash/receipt/payment voucher."""
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "voucher": self._accounting().post_voucher(
                    financial_year_id=context.financial_year_id,
                    voucher_type=str(payload.get("voucher_type", "")),
                    voucher_number=str(payload.get("voucher_number", "")),
                    voucher_date=str(payload.get("voucher_date", "")),
                    narration=str(payload.get("narration", "")),
                    lines=list(payload.get("lines", [])),
                    credit_override_confirmed=bool(
                        payload.get("credit_override_confirmed")
                    ),
                    manager_override_pin=str(payload.get("manager_override_pin", "")),
                )
            }

        return self._write_call(action)

    def check_credit_limit(self, payload: dict[str, Any]) -> dict[str, object]:
        """Preview farmer credit exposure for a pending transaction."""
        def action() -> dict[str, object]:
            context = self._require_context()
            credit_service = CreditLimitService(
                self.databases,
                context.company_id,
            )
            party_id = str(payload.get("party_id", ""))
            account_id = str(payload.get("account_id", ""))
            if not party_id and account_id:
                with self.databases.connect(credit_service.database_path) as connection:
                    resolved = credit_service.party_id_for_account(connection, account_id)
                party_id = resolved or ""
            if not party_id:
                return {
                    "evaluation": {
                        "party_id": "",
                        "party_name": "",
                        "credit_limit_paise": 0,
                        "current_balance_paise": 0,
                        "additional_debit_paise": int(payload.get("additional_debit_paise", 0)),
                        "projected_balance_paise": 0,
                        "available_credit_paise": None,
                        "overage_paise": 0,
                        "status": "normal",
                        "limit_assigned": False,
                        "breached": False,
                    }
                }
            evaluation = credit_service.evaluate_credit(
                party_id=party_id,
                financial_year_id=context.financial_year_id,
                additional_debit_paise=int(payload.get("additional_debit_paise", 0)),
            )
            return {"evaluation": evaluation}

        return self._call(action)

    def farmer_credit_dashboard(
        self,
        group: str = "",
        query: str = "",
    ) -> dict[str, object]:
        """Return farmer credit utilization rows for the dashboard."""
        return self._call(
            lambda: {
                "rows": CreditLimitService(
                    self.databases,
                    self._require_context().company_id,
                ).list_farmer_credit_dashboard(
                    self._require_context().financial_year_id,
                    group=group,
                    query=query,
                )
            }
        )

    def reverse_voucher(
        self,
        voucher_id: str,
        reversal_number: str,
        reversal_date: str,
        reason: str,
    ) -> dict[str, object]:
        """Create an audited opposite voucher instead of deleting history."""
        return self._write_call(
            lambda: {
                "voucher": self._accounting().reverse_voucher(
                    voucher_id,
                    reversal_number,
                    reversal_date,
                    reason,
                )
            }
        )

    def search_documents(
        self,
        document_type: str,
        query: str,
        limit: int = 30,
    ) -> dict[str, object]:
        """Search posted documents for modify mode (newest first)."""
        return self._call(
            lambda: {
                "rows": self._documents().search_posted_documents(
                    self._require_context().financial_year_id,
                    document_type,
                    query,
                    limit=int(limit),
                )
            }
        )

    def get_document(self, document_id: str) -> dict[str, object]:
        """Load a posted document and audit trail for modify mode."""
        return self._call(
            lambda: {
                "document": self._documents().get_document(document_id),
                "audit_trail": self._documents().document_audit_trail(document_id),
            }
        )

    def calculate_document(self, payload: dict[str, Any]) -> dict[str, object]:
        """Preview document calculations without a database write."""
        header = payload.get("header") or {}
        return self._call(
            lambda: {
                "calculation": self._documents().calculate(
                    document_type=str(payload.get("document_type", "")),
                    document_date=str(payload.get("document_date", "")),
                    party_id=payload.get("party_id"),
                    lines=list(payload.get("lines", [])),
                    overrides=payload.get("overrides"),
                    excluded_charge_codes=list(
                        payload.get("excluded_charge_codes", [])
                    ),
                    bonus_paise=int(payload.get("bonus_paise", 0)),
                    bonus_direction=str(header.get("bonus_direction", "add")),
                    freight_paise=int(header.get("freight_paise", 0)),
                    freight_direction=str(header.get("freight_direction", "add")),
                )
            }
        )

    def next_document_number(self, document_type: str) -> dict[str, object]:
        """Return a suggested number for the selected financial year."""
        return self._write_call(
            lambda: {
                "document_number": self._documents().next_document_number(
                    self._require_context().financial_year_id,
                    document_type,
                )
            }
        )

    def post_document(self, payload: dict[str, Any]) -> dict[str, object]:
        """Post a Form-J/Form-I/invoice/challan document."""
        def action() -> dict[str, object]:
            context = self._require_context()
            document = self._documents().post(
                financial_year_id=context.financial_year_id,
                document_type=str(payload.get("document_type", "")),
                document_number=str(payload.get("document_number", "")),
                document_date=str(payload.get("document_date", "")),
                party_id=payload.get("party_id"),
                lines=list(payload.get("lines", [])),
                main_account_id=payload.get("main_account_id"),
                party_account_id=payload.get("party_account_id"),
                overrides=payload.get("overrides"),
                excluded_charge_codes=list(
                    payload.get("excluded_charge_codes", [])
                ),
                bonus_paise=int(payload.get("bonus_paise", 0)),
                header=payload.get("header"),
                credit_override_confirmed=bool(
                    payload.get("credit_override_confirmed")
                ),
                manager_override_pin=str(payload.get("manager_override_pin", "")),
            )
            return {"document": document}

        return self._write_call(action)

    def compliance_status(self) -> dict[str, object]:
        """Return monthly TDS and statutory reminder metadata."""
        return self._call(
            lambda: {
                "compliance": self._reports().compliance_status(
                    self._require_context().financial_year_id
                )
            }
        )

    def dashboard_summary(self) -> dict[str, object]:
        """Return bento dashboard aggregates from local books."""
        return self._call(
            lambda: {
                "dashboard": self._reports().dashboard_summary(
                    self._require_context().financial_year_id
                )
            }
        )

    def trial_balance(self) -> dict[str, object]:
        """Return the selected year's trial balance."""
        return self._call(
            lambda: {
                "rows": self._accounting().trial_balance(
                    self._require_context().financial_year_id
                )
            }
        )

    def stock_balance(self) -> dict[str, object]:
        """Return the selected year's commodity stock balance."""
        return self._call(
            lambda: {
                "rows": self._documents().stock_balance(
                    self._require_context().financial_year_id
                )
            }
        )

    def day_book(self, date_from: str, date_to: str) -> dict[str, object]:
        """Return the selected year's day book."""
        return self._call(
            lambda: {
                "rows": self._reports().day_book(
                    self._require_context().financial_year_id,
                    date_from,
                    date_to,
                )
            }
        )

    def account_ledger(
        self,
        account_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, object]:
        """Return a detailed account ledger."""
        return self._call(
            lambda: {
                "ledger": self._reports().account_ledger(
                    self._require_context().financial_year_id,
                    account_id,
                    date_from,
                    date_to,
                )
            }
        )

    def cash_book(
        self,
        cash_account_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, object]:
        """Return receipt/payment columns and cash-in-hand balance."""
        return self._call(
            lambda: {
                "cash_book": self._reports().cash_book(
                    self._require_context().financial_year_id,
                    cash_account_id,
                    date_from,
                    date_to,
                )
            }
        )

    def tax_register(
        self,
        date_from: str,
        date_to: str,
        tax_family: str,
    ) -> dict[str, object]:
        """Return offline GST, TDS or mandi register rows."""
        return self._call(
            lambda: {
                "rows": self._reports().tax_register(
                    self._require_context().financial_year_id,
                    date_from,
                    date_to,
                    tax_family,
                )
            }
        )

    def financial_statements(self) -> dict[str, object]:
        """Return profit/loss and balance-sheet report sections."""
        return self._call(
            lambda: {
                "statement": self._reports().financial_statements(
                    self._require_context().financial_year_id
                )
            }
        )

    def document_register(
        self,
        document_type: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, object]:
        """Return a typed document register."""
        return self._call(
            lambda: {
                "rows": self._reports().document_register(
                    self._require_context().financial_year_id,
                    document_type,
                    date_from,
                    date_to,
                )
            }
        )

    def calculate_interest(
        self,
        account_id: str,
        date_from: str,
        date_to: str,
        annual_rate: str,
        mode: str = "simple",
    ) -> dict[str, object]:
        """Calculate vyaj (simple or compound) for a selected account and period."""
        return self._call(
            lambda: {
                "interest": self._reports().calculate_simple_interest(
                    self._require_context().financial_year_id,
                    account_id,
                    date_from,
                    date_to,
                    annual_rate,
                    mode=mode,
                )
            }
        )

    def mandi_domain_profile(self) -> dict[str, object]:
        """Return industry/arhat/features flags computed server-side."""
        from .mandi_business import arhat_print_flags
        from .mandi_business import industry_ui_flags

        return self._call(
            lambda: {
                "settings": self._tools().get_company_settings(),
                "industry_ui": industry_ui_flags(self._tools().get_company_settings()),
                "arhat_print": arhat_print_flags(self._tools().get_company_settings()),
            }
        )

    def verify_manager_pin(self, pin: str) -> dict[str, object]:
        """Check manager/admin override PIN for credit limit breaches."""
        from .mandi_business import verify_manager_pin

        return self._call(
            lambda: {
                "ok": verify_manager_pin(self._tools().get_company_settings(), pin)
            }
        )

    def bardana_stock_summary(self) -> dict[str, object]:
        """Return bardana book stock by material type."""
        from .bardana import BardanaService

        context = self._require_context()
        return self._call(
            lambda: {
                "rows": BardanaService(
                    self.databases,
                    context.company_id,
                ).stock_summary(context.financial_year_id)
            }
        )

    def classify_rcm(self, payload: dict[str, Any]) -> dict[str, object]:
        """RCM hint for freight/GTA vs exempt grain handling."""
        from .mandi_business import classify_rcm

        return {
            "rcm": classify_rcm(
                service_category=str(payload.get("service_category", "")),
                is_raw_grain=bool(payload.get("is_raw_grain", False)),
            )
        }

    def compute_apmc_preview(self, payload: dict[str, Any]) -> dict[str, object]:
        """Preview HSAMB/PADB market fee lines for a taxable amount."""
        from .mandi_business import compute_apmc_fees

        settings = self._tools().get_company_settings()
        lines = compute_apmc_fees(
            state=str(payload.get("apmc_state") or settings.get("apmc_state", "haryana")),
            commodity_class=str(payload.get("commodity_class", "grain")),
            taxable_amount_paise=int(payload.get("taxable_amount_paise", 0)),
        )
        return {
            "lines": [
                {
                    "code": line.code,
                    "label": line.label,
                    "rate_percent": str(line.rate_percent),
                    "amount_paise": line.amount_paise,
                }
                for line in lines
            ]
        }

    def rollover_financial_year(self, payload: dict[str, Any]) -> dict[str, object]:
        """Lock prior FY and carry balances into a new financial year."""
        def action() -> dict[str, object]:
            context = self._require_context()
            current_access().assert_user_admin()
            return {
                "rollover": self._accounting().rollover_financial_year(
                    source_financial_year_id=context.financial_year_id,
                    target_start_year=int(payload["target_start_year"]),
                    lock_source=bool(payload.get("lock_source", True)),
                    lock_reason=str(payload.get("lock_reason", "Year-end rollover")),
                )
            }

        return self._write_call(action)

    def create_invoice_pdf(
        self,
        document_id: str,
        destination: str,
        copy_label: str = "original",
    ) -> dict[str, object]:
        """Create a printable A4 PDF for a posted document."""
        return self._call(
            lambda: {
                "path": str(
                    InvoicePrinter(self._documents()).create_pdf(
                        document_id,
                        Path(destination),
                        copy_label,
                    )
                )
            }
        )

    def print_pdf(self, path: str) -> dict[str, object]:
        """Submit a generated PDF to the Windows default printer."""
        return self._call(
            lambda: (
                InvoicePrinter.send_to_default_printer(Path(path)),
                {"submitted": True},
            )[1]
        )

    def print_cash_book_register(
        self,
        cash_account_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, object]:
        """Generate and spool a cash book PDF for the selected period."""
        def action() -> dict[str, object]:
            context = self._require_context()
            cash_book = self._reports().cash_book(
                context.financial_year_id,
                cash_account_id,
                date_from,
                date_to,
            )
            company_name = self._company_display_name()
            destination = Path(tempfile.gettempdir()) / "AnajERP" / "cash-book.pdf"
            RegisterPdfPrinter.cash_book(
                company_name,
                cash_book,
                date_from=date_from,
                date_to=date_to,
                destination=destination,
            )
            RegisterPdfPrinter.print_path(destination)
            return {"path": str(destination), "submitted": True}

        return self._call(action)

    def print_day_book_register(self, date_from: str, date_to: str) -> dict[str, object]:
        """Generate and spool a day book PDF."""
        def action() -> dict[str, object]:
            context = self._require_context()
            rows = self._reports().day_book(
                context.financial_year_id,
                date_from,
                date_to,
            )
            company_name = self._company_display_name()
            destination = Path(tempfile.gettempdir()) / "AnajERP" / "day-book.pdf"
            RegisterPdfPrinter.day_book(
                company_name,
                rows,
                date_from=date_from,
                date_to=date_to,
                destination=destination,
            )
            RegisterPdfPrinter.print_path(destination)
            return {"path": str(destination), "submitted": True}

        return self._call(action)

    def print_voucher(self, voucher_id: str) -> dict[str, object]:
        """Print a posted voucher to the default printer."""
        def action() -> dict[str, object]:
            context = self._require_context()
            with self.databases.connect(
                self.databases.company_path(context.company_id)
            ) as connection:
                voucher = connection.execute(
                    """
                    SELECT voucher_id, voucher_number, voucher_date, voucher_type, narration
                    FROM voucher
                    WHERE voucher_id = ? AND financial_year_id = ?
                    """,
                    (voucher_id, context.financial_year_id),
                ).fetchone()
                if voucher is None:
                    raise ValidationError("Voucher not found")
                lines = connection.execute(
                    """
                    SELECT vl.debit_paise, vl.credit_paise, a.name AS account_name,
                        vl.narration
                    FROM voucher_line vl
                    JOIN account a ON a.account_id = vl.account_id
                    WHERE vl.voucher_id = ?
                    ORDER BY vl.line_number
                    """,
                    (voucher_id,),
                ).fetchall()
            company_name = self._company_display_name()
            destination = Path(tempfile.gettempdir()) / "AnajERP" / f"{voucher_id}.pdf"
            RegisterPdfPrinter.voucher(
                company_name,
                dict(voucher),
                [dict(row) for row in lines],
                destination,
            )
            RegisterPdfPrinter.print_path(destination)
            return {"path": str(destination), "submitted": True}

        return self._call(action)

    def run_diagnostics(self) -> dict[str, object]:
        """Extended health check for administrators (reconcile + catalog metadata)."""
        def action() -> dict[str, object]:
            context = self._require_context()
            reconciliation = MaintenanceService(
                self.databases,
                context.company_id,
            ).reconcile(context.financial_year_id)
            with self.databases.connect(
                self.databases.company_path(context.company_id)
            ) as connection:
                schema_row = connection.execute(
                    "SELECT MAX(version) AS v FROM schema_version"
                ).fetchone()
            return {
                "diagnostics": {
                    "reconciliation": reconciliation,
                    "company_schema_version": int(schema_row["v"] or 0)
                    if schema_row
                    else 0,
                    "installation_id": self.databases.installation_id(),
                }
            }

        return self._call(action)

    def merge_parties(self, source_party_id: str, target_party_id: str) -> dict[str, object]:
        """Merge duplicate party masters (admin tool)."""
        def action() -> dict[str, object]:
            return self._tools().merge_parties(source_party_id, target_party_id)

        return self._write_call(action)

    def print_document(self, document_id: str) -> dict[str, object]:
        """Print posted mandi documents (silent ESC/POS by default during harvest)."""
        return self.print_mandi_bill(
            {
                "document_id": document_id,
                "copies": 3,
                "format": "auto",
                "silent": True,
            }
        )

    def preview_mandi_statutory_html(self, payload: dict[str, Any]) -> dict[str, object]:
        """Render statutory Form-J / Form-I HTML (multi-copy) for screen preview."""
        from .mandi_bills import MandiBillPrinter

        def action() -> dict[str, object]:
            document_id = str(payload.get("document_id", "")).strip()
            if not document_id:
                raise ValidationError("document_id is required")
            settings = self._tools().get_company_settings()
            design = settings.get("print_design") or {}
            html_columns = int(payload.get("html_columns", 80))
            copies = int(payload.get("copies", 3))
            printer = MandiBillPrinter(self._documents())
            out_dir = Path(tempfile.gettempdir()) / "AnajERP" / "print"
            path = printer.create_statutory_html(
                document_id,
                out_dir / f"{document_id}-statutory",
                columns=html_columns,
                copy_count=copies,
                design=design,
            )
            return {"path": str(path), "format": "html", "copies": min(max(copies, 1), 3)}

        return self._call(action)

    def print_mandi_bill(self, payload: dict[str, Any]) -> dict[str, object]:
        """Print J/I forms: ESC/POS silent raw, statutory HTML, or PDF copies."""
        from .escpos import spool_escpos_raw, try_windows_raw_print
        from .mandi_bills import MandiBillPrinter
        from .mandi_webview_print import print_html_file

        MANDI_STATUTORY_TYPES = frozenset(
            {"form_j", "form_i_credit", "form_i_debit", "sale_invoice"}
        )

        def action() -> dict[str, object]:
            document_id = str(payload.get("document_id", "")).strip()
            if not document_id:
                raise ValidationError("document_id is required")
            settings = self._tools().get_company_settings()
            design = settings.get("print_design") or {}
            visible = dict(payload.get("visible_columns") or {})
            copies = int(payload.get("copies", 3))
            silent = bool(payload.get("silent", True))
            fmt = str(payload.get("format") or "auto").strip().lower()
            html_columns = int(payload.get("html_columns", 80))
            escpos_columns = int(payload.get("escpos_columns", html_columns if html_columns in {80, 132} else 80))
            printer = MandiBillPrinter(self._documents())
            header = printer.documents.get_document(document_id)["header"]
            doc_type = str(header.get("document_type") or "")
            use_escpos = payload.get("use_escpos")
            if use_escpos is None:
                use_escpos = doc_type in MANDI_STATUTORY_TYPES and silent
            else:
                use_escpos = bool(use_escpos)
            if fmt == "auto":
                fmt = "escpos" if use_escpos else "html"
            out_dir = Path(tempfile.gettempdir()) / "AnajERP" / "print"
            out_dir.mkdir(parents=True, exist_ok=True)
            if fmt == "escpos" or (fmt == "html" and silent and use_escpos):
                raw = printer.create_escpos_copies(
                    document_id,
                    columns=escpos_columns,
                    copy_count=copies,
                    design=design,
                    visible_columns=visible,
                )
                spool_path = spool_escpos_raw(
                    raw,
                    out_dir / f"{document_id}.escpos",
                )
                sent_raw = try_windows_raw_print(
                    raw,
                    str(payload.get("printer_name", "") or "") or None,
                )
                return {
                    "ok": True,
                    "path": str(spool_path),
                    "submitted": sent_raw,
                    "format": "escpos",
                    "bytes": len(raw),
                    "copies": min(max(copies, 1), 3),
                    "silent": True,
                }
            if fmt == "html":
                html_path = printer.create_statutory_html(
                    document_id,
                    out_dir / f"{document_id}-statutory",
                    columns=html_columns,
                    copy_count=copies,
                    design=design,
                )
                submitted = print_html_file(html_path, silent=silent)
                return {
                    "ok": True,
                    "path": str(html_path),
                    "submitted": submitted and not silent,
                    "format": "html",
                    "copies": min(max(copies, 1), 3),
                    "silent": silent,
                }
            paths: list[str] = []
            copy_labels = ["original", "duplicate", "triplicate"]
            for index in range(min(copies, 3)):
                label = copy_labels[index]
                destination = out_dir / f"{document_id}-{label}.pdf"
                pdf_path = printer.create_mandi_pdf(
                    document_id,
                    destination,
                    copy_label=label,
                    design=design,
                    visible_columns=visible,
                )
                paths.append(str(pdf_path))
                if not silent:
                    InvoicePrinter.send_to_default_printer(pdf_path)
            return {
                "ok": True,
                "paths": paths,
                "submitted": not silent and bool(paths),
                "format": "pdf",
                "copies": len(paths),
                "silent": silent,
            }

        return self._call(action)

    def export_table(self, payload: dict[str, Any]) -> dict[str, object]:
        """Export arbitrary tabular report data to xlsx/csv/pdf/docx/xml/html/png/jpeg."""
        from .export_engine import TableExportEngine

        def action() -> dict[str, object]:
            file_format = str(payload.get("format", "csv"))
            title = str(payload.get("title", "Report"))
            columns = list(payload.get("columns") or [])
            rows = list(payload.get("rows") or [])
            visible = payload.get("visible_columns")
            folder = Path(str(payload.get("destination_dir", ""))).expanduser()
            if not str(folder).strip():
                folder = Path(tempfile.gettempdir()) / "AnajERP" / "exports"
            safe = "".join(ch if ch.isalnum() else "_" for ch in title)[:40] or "report"
            destination = folder / safe
            engine = TableExportEngine(
                title=title,
                columns=columns,
                rows=rows,
                visible_columns=list(visible) if visible else None,
            )
            path = engine.export(destination, file_format)
            return {"path": str(path), "format": file_format, "row_count": len(rows)}

        return self._call(action)

    def get_print_design(self) -> dict[str, object]:
        from .print_designer import merge_print_design

        return self._call(
            lambda: {
                "design": merge_print_design(
                    self._tools().get_company_settings().get("print_design")
                )
            }
        )

    def save_print_design(self, design: dict[str, Any]) -> dict[str, object]:
        def action() -> dict[str, object]:
            settings = self._tools().get_company_settings()
            settings["print_design"] = design
            self._tools().save_company_settings(settings)
            return {"saved": True}

        return self._write_call(action)

    def print_party_ledger(self, payload: dict[str, Any]) -> dict[str, object]:
        """Muddat Bilti / Nakal Khata PDF for a party ledger."""
        from .mandi_bills import MandiBillPrinter

        def action() -> dict[str, object]:
            context = self._require_context()
            account_id = str(payload.get("account_id", "")).strip()
            date_from = str(payload.get("date_from", ""))
            date_to = str(payload.get("date_to", ""))
            if not account_id:
                raise ValidationError("account_id is required")
            ledger = self._reports().account_ledger(
                context.financial_year_id,
                account_id,
                date_from,
                date_to,
            )
            rows: list[dict[str, str]] = []
            balance = int(ledger.get("opening_balance_paise", 0))
            for entry in ledger.get("entries", []):
                debit = int(entry.get("debit_paise", 0))
                credit = int(entry.get("credit_paise", 0))
                balance += debit - credit
                rows.append(
                    {
                        "date": str(entry.get("voucher_date", "")),
                        "particulars": str(entry.get("narration", "")),
                        "debit": f"{debit / 100:.2f}" if debit else "",
                        "credit": f"{credit / 100:.2f}" if credit else "",
                        "balance": f"{balance / 100:.2f}",
                    }
                )
            title = str(payload.get("title", "Nakal Khata / Muddat Bilti"))
            design = self._tools().get_company_settings().get("print_design")
            destination = Path(tempfile.gettempdir()) / "AnajERP" / f"ledger-{account_id}.pdf"
            path = MandiBillPrinter(self._documents()).ledger_statement_pdf(
                party_name=str(ledger.get("account_name", "")),
                rows=rows,
                destination=destination,
                title=title,
                design=design if isinstance(design, dict) else None,
            )
            InvoicePrinter.send_to_default_printer(path)
            return {"path": str(path), "submitted": True}

        return self._call(action)

    def create_backup(self, destination: str) -> dict[str, object]:
        """Create a checked company backup package."""

        def action() -> dict[str, object]:
            context = self._require_context()
            backup_path = BackupService(self.databases).create_company_backup(
                context.company_id,
                Path(destination),
            )
            settings = self._tools().get_company_settings()
            drive = apply_google_drive_backup(backup_path, settings)
            return {"path": str(backup_path), **drive}

        return self._call(action)

    def restore_new_company(self, source: str) -> dict[str, object]:
        """Restore a backup as a company without overwriting existing data."""
        return self._write_call(
            lambda: {
                "company": BackupService(self.databases).restore_new_company(
                    Path(source)
                )
            }
        )

    def import_master_csv(
        self,
        entity_type: str,
        source: str,
        dry_run: bool = True,
    ) -> dict[str, object]:
        """Dry-run or execute a pilot master-data CSV import."""
        def action() -> dict[str, object]:
            return {
                "migration": MaintenanceService(
                    self.databases,
                    self._require_context().company_id,
                ).import_master_csv(
                    entity_type,
                    Path(source),
                    dry_run=bool(dry_run),
                )
            }

        return self._call(action) if dry_run else self._write_call(action)

    def reconcile_company(self) -> dict[str, object]:
        """Run release-grade accounting and database consistency checks."""
        return self._call(
            lambda: {
                "reconciliation": MaintenanceService(
                    self.databases,
                    self._require_context().company_id,
                ).reconcile(self._require_context().financial_year_id)
            }
        )

    def list_cities(self) -> dict[str, object]:
        return self._call(lambda: {"cities": self._masters().list_cities()})

    def save_city(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(lambda: {"city": self._masters().save_city(payload)})

    def get_city(self, city_id: str) -> dict[str, object]:
        return self._call(lambda: {"city": self._masters().get_city(city_id)})

    def delete_city(self, city_id: str) -> dict[str, object]:
        return self._write_call(lambda: {"city": self._masters().delete_city(city_id)})

    def list_transports(self) -> dict[str, object]:
        return self._call(lambda: {"transports": self._masters().list_transports()})

    def save_transport(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {"transport": self._masters().save_transport(payload)}
        )

    def get_transport(self, transport_id: str) -> dict[str, object]:
        return self._call(lambda: {"transport": self._masters().get_transport(transport_id)})

    def delete_transport(self, transport_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {"transport": self._masters().delete_transport(transport_id)}
        )

    def list_narrations(self) -> dict[str, object]:
        return self._call(lambda: {"narrations": self._masters().list_narrations()})

    def save_narration(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {"narration": self._masters().save_narration(payload)}
        )

    def get_narration(self, narration_id: str) -> dict[str, object]:
        return self._call(lambda: {"narration": self._masters().get_narration(narration_id)})

    def delete_narration(self, narration_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {"narration": self._masters().delete_narration(narration_id)}
        )

    def list_banks(self) -> dict[str, object]:
        return self._call(lambda: {"banks": self._masters().list_banks()})

    def get_bank(self, bank_key: str) -> dict[str, object]:
        return self._call(lambda: {"bank": self._masters().get_bank(bank_key)})

    def save_bank(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(lambda: {"bank": self._masters().save_bank(payload)})

    def delete_bank(self, bank_key: str) -> dict[str, object]:
        return self._write_call(lambda: {"bank": self._masters().delete_bank(bank_key)})

    def list_ifsc_codes(self) -> dict[str, object]:
        return self._call(lambda: {"ifsc_codes": self._masters().list_ifsc()})

    def get_ifsc_code(self, ifsc_key: str) -> dict[str, object]:
        return self._call(lambda: {"ifsc": self._masters().get_ifsc(ifsc_key)})

    def save_ifsc_code(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(lambda: {"ifsc": self._masters().save_ifsc(payload)})

    def delete_ifsc_code(self, ifsc_key: str) -> dict[str, object]:
        return self._write_call(lambda: {"ifsc": self._masters().delete_ifsc(ifsc_key)})

    def list_expense_masters(self) -> dict[str, object]:
        return self._call(
            lambda: {"expense_masters": self._masters().list_expense_masters()}
        )

    def save_expense_master(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {"expense_master": self._masters().save_expense_master(payload)}
        )

    def get_expense_master(self, expense_master_id: str) -> dict[str, object]:
        return self._call(
            lambda: {"expense_master": self._masters().get_expense_master(expense_master_id)}
        )

    def delete_expense_master(self, expense_master_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {"expense_master": self._masters().delete_expense_master(expense_master_id)}
        )

    def list_cheque_print_settings(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "cheque_print_settings": self._masters().list_cheque_print_settings()
            }
        )

    def get_cheque_print_setting(self, setting_key: str) -> dict[str, object]:
        return self._call(
            lambda: {
                "cheque_print_setting": self._masters().get_cheque_print_setting(
                    setting_key
                )
            }
        )

    def save_cheque_print_setting(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "cheque_print_setting": self._masters().save_cheque_print_setting(
                    payload
                )
            }
        )

    def delete_cheque_print_setting(self, setting_key: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "cheque_print_setting": self._masters().delete_cheque_print_setting(
                    setting_key
                )
            }
        )

    def list_i_form_expense_defines(
        self, commodity_id: str = ""
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "defines": self._masters().list_i_form_expense_defines(commodity_id)
            }
        )

    def get_i_form_expense_define(
        self, commodity_id: str, effective_date: str
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "define": self._masters().get_i_form_expense_define(
                    commodity_id, effective_date
                )
            }
        )

    def save_i_form_expense_define(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {"define": self._masters().save_i_form_expense_define(payload)}
        )

    def delete_i_form_expense_define(self, define_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {"define": self._masters().delete_i_form_expense_define(define_id)}
        )

    def list_items(self) -> dict[str, object]:
        return self._call(lambda: {"items": self._masters().list_items()})

    def list_trading_accounts(self) -> dict[str, object]:
        return self._call(
            lambda: {"trading_accounts": self._masters().list_trading_accounts()}
        )

    def get_trading_account(self, trading_account_id: str) -> dict[str, object]:
        return self._call(
            lambda: {"trading_account": self._masters().get_trading_account(trading_account_id)}
        )

    def save_trading_account(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {"trading_account": self._masters().save_trading_account(payload)}
        )

    def delete_trading_account(self, trading_account_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {"trading_account": self._masters().delete_trading_account(trading_account_id)}
        )

    def save_item_master(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(lambda: {"item": self._masters().save_item(payload)})

    def get_item(self, commodity_id: str) -> dict[str, object]:
        return self._call(lambda: {"item": self._masters().get_item(commodity_id)})

    def delete_item(self, commodity_id: str) -> dict[str, object]:
        return self._write_call(lambda: {"item": self._masters().delete_item(commodity_id)})

    def save_account_master(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {"account_master": self._masters().save_account_master(payload)}
        )

    def get_party_master(self, party_id: str) -> dict[str, object]:
        return self._call(
            lambda: {"party": self._masters().get_party_master(party_id)}
        )

    def get_account_master(self, account_id: str) -> dict[str, object]:
        return self._call(
            lambda: {"party": self._masters().get_account_master(account_id)}
        )

    def delete_account_master(self, account_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {"account_master": self._masters().delete_account_master(account_id)}
        )

    def lookup_gstin(self, gstin: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            settings = self._tools().get_company_settings()
            return {"taxpayer": lookup_gstin_online(gstin, settings)}

        return self._call(action)

    def discover_lan_servers(self, timeout_seconds: float = 2.5) -> dict[str, object]:
        """Standalone build — LAN discovery disabled (see extra_code_Lan_Office)."""
        _ = timeout_seconds
        return self._result(servers=[], standalone=True)

    def lan_office_beacon(self, http_port: int = 8765) -> dict[str, object]:
        _ = http_port
        return self._result(
            beacon={"standalone": True, "message": "LAN office server is not used in standalone mode"}
        )

    def acquire_document_lock(
        self,
        resource_key: str,
        holder_label: str = "",
        ttl_seconds: float | None = None,
    ) -> dict[str, object]:
        def action() -> dict[str, object]:
            access = current_access()
            holder = access.user_id
            label = holder_label or access.username
            result = standalone_runtime.lock_coordinator.acquire(
                resource_key,
                holder,
                label,
                ttl_seconds=ttl_seconds,
            )
            if result.get("ok"):
                standalone_runtime.live_hub.broadcast(
                    "lock",
                    {"action": "acquire", **result},
                )
            return result

        return self._write_call(action)

    def release_document_lock(self, resource_key: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            holder = current_access().user_id
            result = standalone_runtime.lock_coordinator.release(resource_key, holder)
            if result.get("ok"):
                standalone_runtime.live_hub.broadcast(
                    "lock",
                    {"action": "release", "resource_key": resource_key},
                )
            return result

        return self._write_call(action)

    def document_lock_status(self, resource_key: str) -> dict[str, object]:
        return self._call(
            lambda: standalone_runtime.lock_coordinator.status(resource_key),
        )

    def list_document_locks(self) -> dict[str, object]:
        return self._call(lambda: {"locks": standalone_runtime.lock_coordinator.snapshot()})

    def fetch_mandi_bhav(
        self,
        state: str = "",
        commodity: str = "",
        limit: int = 40,
    ) -> dict[str, object]:
        def action() -> dict[str, object]:
            settings = self._tools().get_company_settings()
            payload = fetch_mandi_bhav(
                settings,
                state=state,
                commodity=commodity,
                limit=int(limit),
            )
            standalone_runtime.live_hub.broadcast("mandi_bhav", payload)
            return payload

        return self._call(action)

    def auction_board_snapshot(self) -> dict[str, object]:
        return self._call(lambda: {"lots": standalone_runtime.auction_board.list_lots()})

    def upsert_auction_lot(self, payload: dict[str, Any]) -> dict[str, object]:
        def action() -> dict[str, object]:
            result = standalone_runtime.auction_board.upsert_lot(payload)
            if result.get("ok"):
                standalone_runtime.live_hub.broadcast("auction", result)
            return result

        return self._write_call(action)

    def place_auction_bid(self, payload: dict[str, Any]) -> dict[str, object]:
        def action() -> dict[str, object]:
            result = standalone_runtime.auction_board.place_bid(payload)
            if result.get("ok"):
                standalone_runtime.live_hub.broadcast("auction", result)
            return result

        return self._write_call(action)

    def close_auction_lot(self, lot_id: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            result = standalone_runtime.auction_board.close_lot(lot_id)
            if result.get("ok"):
                standalone_runtime.live_hub.broadcast("auction", result)
            return result

        return self._write_call(action)

    def start_cloud_oauth(self, provider: str) -> dict[str, object]:
        return self._call(
            lambda: start_oauth_device_flow(
                provider,
                self._tools().get_company_settings(),
            ),
        )

    def poll_cloud_oauth(
        self,
        provider: str,
        device_code: str,
    ) -> dict[str, object]:
        def action() -> dict[str, object]:
            settings = self._tools().get_company_settings()
            polled = poll_oauth_device_flow(provider, device_code, settings)
            if polled.get("ok") and polled.get("tokens"):
                token_key = str(polled.get("token_key") or "")
                tokens = polled["tokens"]
                if token_key:
                    settings[token_key] = tokens
                    self._tools().save_company_settings(settings)
            return polled

        return self._write_call(action)

    def run_encrypted_cloud_backup(self, destination: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            settings = self._tools().get_company_settings()
            passphrase = str(settings.get("cloud_backup_passphrase") or "").strip()
            if len(passphrase) < 8:
                raise ValidationError("Set cloud backup passphrase (8+ chars) first")
            dest = Path(destination)
            dest.mkdir(parents=True, exist_ok=True)
            backup_path = BackupService(self.databases).create_company_backup(
                context.company_id,
                dest,
            )
            encrypted = encrypt_file(
                backup_path,
                dest / f"{backup_path.stem}.bak.enc",
                passphrase,
            )
            uploaded = upload_encrypted_backup(encrypted, settings)
            return {"encrypted_path": str(encrypted), **uploaded}

        return self._write_call(action)

    def run_exit_cloud_backup_if_enabled(self) -> dict[str, object]:
        """Called on desktop shutdown when cloud backup on exit is enabled."""
        try:
            context = self._context
            if context is None:
                return self._result(skipped=True, reason="no_active_context")
            settings = self._tools().get_company_settings()
            dest = Path(
                str(settings.get("default_backup_path") or tempfile.gettempdir())
            )
            result = run_exit_cloud_backup(
                self.databases,
                context.company_id,
                settings,
                dest,
            )
            return self._result(**result)
        except (AnajError, ValueError, TypeError, OSError) as exc:
            return self._error(exc)

    def save_opening_stock(self, payload: dict[str, Any]) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "opening_stock": self._masters().save_opening_stock(
                    context.financial_year_id,
                    payload,
                )
            }

        return self._write_call(action)

    def list_stock_entries(self, entry_kind: str = "") -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "stock_entries": self._masters().list_stock_entries(
                    context.financial_year_id,
                    entry_kind,
                )
            }

        return self._call(action)

    def get_stock_entry_master(
        self,
        stock_entry_id: str = "",
        entry_kind: str = "",
        entry_date: str = "",
        search_item: str = "",
    ) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "stock_entry": self._masters().get_stock_entry(
                    context.financial_year_id,
                    stock_entry_id,
                    entry_kind=entry_kind,
                    entry_date=entry_date,
                    search_item=search_item,
                )
            }

        return self._call(action)

    def save_stock_entry_master(self, payload: dict[str, Any]) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "stock_entry": self._masters().save_stock_entry_master(
                    context.financial_year_id,
                    payload,
                )
            }

        return self._write_call(action)

    def delete_stock_entry_master(self, stock_entry_id: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "stock_entry": self._masters().delete_stock_entry_master(
                    context.financial_year_id,
                    stock_entry_id,
                )
            }

        return self._write_call(action)

    def get_gst_purchase_entry(
        self,
        document_id: str = "",
        entry_date: str = "",
        party_id: str = "",
        bill_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "gst_purchase_entry": self._gst_purchase().get_gst_purchase_entry(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    entry_date=entry_date,
                    party_id=party_id,
                    bill_no=bill_no,
                )
            }
        )

    def save_gst_purchase_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "gst_purchase_entry": self._gst_purchase().save_gst_purchase_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_gst_purchase_entry(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "gst_purchase_entry": self._gst_purchase().delete_gst_purchase_entry(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def lookup_gst_items(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_purchase().lookup_items(query)})

    def lookup_gst_parties(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_purchase().lookup_parties(query)})

    def lookup_gst_purchase_accounts(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_purchase().lookup_purchase_accounts(query)})

    def next_gst_entry_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "document_number": self._gst_purchase().next_entry_number(
                    self._require_context().financial_year_id,
                )
            }
        )

    def get_invoice_entry(
        self,
        document_id: str = "",
        entry_date: str = "",
        party_id: str = "",
        bill_no: str = "",
        book_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "invoice_entry": self._invoice().get_invoice_entry(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    entry_date=entry_date,
                    party_id=party_id,
                    bill_no=bill_no,
                    book_no=book_no,
                )
            }
        )

    def save_invoice_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "invoice_entry": self._invoice().save_invoice_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_invoice_entry(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "invoice_entry": self._invoice().delete_invoice_entry(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def lookup_invoice_items(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._invoice().lookup_items(query)})

    def lookup_invoice_parties(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._invoice().lookup_parties(query)})

    def lookup_invoice_sale_accounts(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._invoice().lookup_sale_accounts(query)})

    def lookup_invoice_brokers(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._invoice().lookup_broker_accounts(query)})

    def next_invoice_entry_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "document_number": self._invoice().next_entry_number(
                    self._require_context().financial_year_id,
                )
            }
        )

    def get_gst_debit_note_entry(
        self,
        document_id: str = "",
        entry_date: str = "",
        party_id: str = "",
        d_note_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "gst_debit_note_entry": self._gst_debit_note().get_gst_debit_note_entry(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    entry_date=entry_date,
                    party_id=party_id,
                    d_note_no=d_note_no,
                )
            }
        )

    def save_gst_debit_note_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "gst_debit_note_entry": self._gst_debit_note().save_gst_debit_note_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_gst_debit_note_entry(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "gst_debit_note_entry": self._gst_debit_note().delete_gst_debit_note_entry(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def lookup_gst_debit_note_parties(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_debit_note().lookup_parties(query)})

    def lookup_gst_debit_note_accounts(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_debit_note().lookup_line_accounts(query)})

    def lookup_gst_debit_note_items(
        self,
        party_id: str,
        pur_sale: str = "S",
        query: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._gst_debit_note().lookup_line_items(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    pur_sale=pur_sale,
                    query=query,
                )
            }
        )

    def lookup_gst_debit_note_rates(
        self,
        party_id: str,
        commodity_id: str,
        pur_sale: str = "S",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._gst_debit_note().lookup_line_rates(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    commodity_id=commodity_id,
                    pur_sale=pur_sale,
                )
            }
        )

    def fill_gst_debit_note_from_document(
        self,
        party_id: str,
        doc_no: str,
        pur_sale: str = "S",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "fill": self._gst_debit_note().fill_from_source_document(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    doc_no=doc_no,
                    pur_sale=pur_sale,
                )
            }
        )

    def next_gst_debit_note_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "document_number": self._gst_debit_note().next_entry_number(
                    self._require_context().financial_year_id,
                )
            }
        )

    def get_gst_credit_note_entry(
        self,
        document_id: str = "",
        entry_date: str = "",
        party_id: str = "",
        c_note_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "gst_credit_note_entry": self._gst_credit_note().get_gst_credit_note_entry(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    entry_date=entry_date,
                    party_id=party_id,
                    c_note_no=c_note_no,
                )
            }
        )

    def save_gst_credit_note_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "gst_credit_note_entry": self._gst_credit_note().save_gst_credit_note_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_gst_credit_note_entry(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "gst_credit_note_entry": self._gst_credit_note().delete_gst_credit_note_entry(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def lookup_gst_credit_note_parties(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_credit_note().lookup_parties(query)})

    def lookup_gst_credit_note_accounts(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_credit_note().lookup_line_accounts(query)})

    def lookup_gst_credit_note_items(
        self,
        party_id: str,
        pur_sale: str = "S",
        query: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._gst_credit_note().lookup_line_items(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    pur_sale=pur_sale,
                    query=query,
                )
            }
        )

    def lookup_gst_credit_note_rates(
        self,
        party_id: str,
        commodity_id: str,
        pur_sale: str = "S",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._gst_credit_note().lookup_line_rates(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    commodity_id=commodity_id,
                    pur_sale=pur_sale,
                )
            }
        )

    def fill_gst_credit_note_from_document(
        self,
        party_id: str,
        doc_no: str,
        pur_sale: str = "S",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "fill": self._gst_credit_note().fill_from_source_document(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    doc_no=doc_no,
                    pur_sale=pur_sale,
                )
            }
        )

    def next_gst_credit_note_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "document_number": self._gst_credit_note().next_entry_number(
                    self._require_context().financial_year_id,
                )
            }
        )

    def get_gst_expense_voucher_entry(
        self,
        document_id: str = "",
        entry_date: str = "",
        party_id: str = "",
        voucher_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "gst_expense_voucher_entry": self._gst_expense_voucher().get_gst_expense_voucher_entry(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    entry_date=entry_date,
                    party_id=party_id,
                    voucher_no=voucher_no,
                )
            }
        )

    def save_gst_expense_voucher_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "gst_expense_voucher_entry": self._gst_expense_voucher().save_gst_expense_voucher_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_gst_expense_voucher_entry(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "gst_expense_voucher_entry": self._gst_expense_voucher().delete_gst_expense_voucher_entry(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def lookup_gst_expense_voucher_parties(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_expense_voucher().lookup_parties(query)})

    def lookup_gst_expense_voucher_accounts(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_expense_voucher().lookup_line_accounts(query)})

    def lookup_gst_expense_voucher_items(
        self,
        party_id: str,
        query: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._gst_expense_voucher().lookup_line_items(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    query=query,
                )
            }
        )

    def lookup_gst_expense_voucher_rates(
        self,
        party_id: str,
        commodity_id: str,
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._gst_expense_voucher().lookup_line_rates(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    commodity_id=commodity_id,
                )
            }
        )

    def fill_gst_expense_voucher_from_document(
        self,
        party_id: str,
        doc_no: str,
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "fill": self._gst_expense_voucher().fill_from_source_document(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    doc_no=doc_no,
                )
            }
        )

    def next_gst_expense_voucher_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "document_number": self._gst_expense_voucher().next_entry_number(
                    self._require_context().financial_year_id,
                )
            }
        )

    def get_debit_note_entry(
        self,
        document_id: str = "",
        note_date: str = "",
        party_id: str = "",
        note_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "debit_note_entry": self._debit_note().get_note_entry(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    note_date=note_date,
                    party_id=party_id,
                    note_no=note_no,
                )
            }
        )

    def save_debit_note_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "debit_note_entry": self._debit_note().save_note_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_debit_note_entry(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "debit_note_entry": self._debit_note().delete_note_entry(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def get_credit_note_entry(
        self,
        document_id: str = "",
        note_date: str = "",
        party_id: str = "",
        note_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "credit_note_entry": self._credit_note().get_note_entry(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    note_date=note_date,
                    party_id=party_id,
                    note_no=note_no,
                )
            }
        )

    def save_credit_note_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "credit_note_entry": self._credit_note().save_note_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_credit_note_entry(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "credit_note_entry": self._credit_note().delete_note_entry(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def lookup_debit_note_parties(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._debit_note().lookup_parties(query)})

    def lookup_credit_note_parties(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._credit_note().lookup_parties(query)})

    def lookup_debit_note_accounts(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._debit_note().lookup_accounts(query)})

    def lookup_credit_note_accounts(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._credit_note().lookup_accounts(query)})

    def lookup_debit_note_items(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._debit_note().lookup_items(query)})

    def lookup_credit_note_items(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._credit_note().lookup_items(query)})

    def next_debit_note_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "document_number": self._debit_note().next_entry_number(
                    self._require_context().financial_year_id,
                )
            }
        )

    def next_credit_note_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "document_number": self._credit_note().next_entry_number(
                    self._require_context().financial_year_id,
                )
            }
        )

    def get_voucher_entry(
        self,
        voucher_id: str = "",
        voucher_number: str = "",
        voucher_date: str = "",
        voucher_type: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "voucher_entry": self._voucher_entry().get_voucher_entry(
                    self._require_context().financial_year_id,
                    voucher_id=voucher_id,
                    voucher_number=voucher_number,
                    voucher_date=voucher_date,
                    voucher_type=voucher_type,
                )
            }
        )

    def save_voucher_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "voucher_entry": self._voucher_entry().save_voucher_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_voucher_entry(self, voucher_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "voucher_entry": self._voucher_entry().delete_voucher_entry(
                    self._require_context().financial_year_id,
                    voucher_id,
                )
            }
        )

    def lookup_voucher_entry_accounts(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._voucher_entry().lookup_accounts(query)})

    def lookup_voucher_entry_banks(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._voucher_entry().lookup_bank_accounts(query)})

    def voucher_entry_account_balance(
        self,
        account_id: str,
        as_of_date: str,
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "balance_paise": self._voucher_entry().account_balance_paise(
                    self._require_context().financial_year_id,
                    account_id,
                    as_of_date,
                )
            }
        )

    def voucher_entry_cash_in_hand(self, as_of_date: str) -> dict[str, object]:
        return self._call(
            lambda: self._voucher_entry().cash_in_hand_paise(
                self._require_context().financial_year_id,
                as_of_date,
            )
        )

    def voucher_entry_line_hints(self, account_id: str) -> dict[str, object]:
        return self._call(
            lambda: {
                "hints": self._voucher_entry().last_line_hints(
                    self._require_context().financial_year_id,
                    account_id,
                )
            }
        )

    def next_voucher_entry_number(self, voucher_type: str = "Receipt") -> dict[str, object]:
        return self._call(
            lambda: {
                "voucher_number": self._voucher_entry().next_voucher_number(
                    self._require_context().financial_year_id,
                    voucher_type,
                )
            }
        )

    def list_tds_challan_deductee_codes(self) -> dict[str, object]:
        return self._call(lambda: {"rows": self._tds_challan().list_deductee_codes()})

    def list_tds_challan_pending_lines(
        self,
        date_from: str,
        date_to: str,
        deductee_code: str = "All",
        challan_id: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._tds_challan().list_pending_lines(
                    self._require_context().financial_year_id,
                    date_from,
                    date_to,
                    deductee_code,
                    challan_id=challan_id,
                )
            }
        )

    def get_tds_challan_entry(
        self,
        challan_id: str = "",
        challan_display_id: str = "",
        challan_date: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "tds_challan_entry": self._tds_challan().get_challan_entry(
                    self._require_context().financial_year_id,
                    challan_id=challan_id,
                    challan_display_id=challan_display_id,
                    challan_date=challan_date,
                )
            }
        )

    def save_tds_challan_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "tds_challan_entry": self._tds_challan().save_challan_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_tds_challan_entry(self, challan_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "tds_challan_entry": self._tds_challan().delete_challan_entry(
                    self._require_context().financial_year_id,
                    challan_id,
                )
            }
        )

    def next_tds_challan_display_id(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "challan_display_id": self._tds_challan().next_challan_id(
                    self._require_context().financial_year_id,
                )
            }
        )

    def search_bank_reconciliation(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._bank_reconciliation().search_lines(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def set_bank_reconciliation(self, voucher_line_ids: list[str], reconciled: bool) -> dict[str, object]:
        return self._write_call(
            lambda: self._bank_reconciliation().set_reconciled(
                self._require_context().financial_year_id,
                voucher_line_ids,
                reconciled,
            )
        )

    def export_bank_reconciliation(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: self._bank_reconciliation().export_excel_csv(
                self._require_context().financial_year_id,
                payload,
            )
        )

    def print_bank_reconciliation(self, payload: dict[str, Any]) -> dict[str, object]:
        ctx = self._require_context()
        company_name = self._company_display_name()
        return self._write_call(
            lambda: self._bank_reconciliation().print_report(
                ctx.financial_year_id,
                payload,
                company_name=company_name,
            )
        )

    def get_mandi_purchase_entry(
        self,
        document_id: str = "",
        entry_date: str = "",
        purchase_party_id: str = "",
        document_number: str = "",
        line_bill_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "mandi_purchase_entry": self._mandi_purchase().get_mandi_purchase_entry(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    entry_date=entry_date,
                    purchase_party_id=purchase_party_id,
                    document_number=document_number,
                    line_bill_no=line_bill_no,
                )
            }
        )

    def save_mandi_purchase_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "mandi_purchase_entry": self._mandi_purchase().save_mandi_purchase_entry(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_mandi_purchase_entry(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "mandi_purchase_entry": self._mandi_purchase().delete_mandi_purchase_entry(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def lookup_mandi_parties(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._mandi_purchase().lookup_parties(query)})

    def lookup_mandi_items(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._mandi_purchase().lookup_items(query)})

    def lookup_mandi_line_rates(
        self,
        line_party_id: str,
        commodity_id: str,
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._mandi_purchase().lookup_line_rates(
                    self._require_context().financial_year_id,
                    line_party_id=line_party_id,
                    commodity_id=commodity_id,
                )
            }
        )

    def next_mandi_entry_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "document_number": self._mandi_purchase().next_entry_number(
                    self._require_context().financial_year_id,
                )
            }
        )

    def get_kachi_purchase(
        self,
        document_id: str = "",
        entry_date: str = "",
        po_no: str = "",
        buyer_party_id: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "kachi_purchase": self._kachi().get_kachi_purchase(
                    self._require_context().financial_year_id,
                    document_id=document_id,
                    entry_date=entry_date,
                    po_no=po_no,
                    buyer_party_id=buyer_party_id,
                )
            }
        )

    def save_kachi_purchase(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "kachi_purchase": self._kachi().save_kachi_purchase(
                    self._require_context().financial_year_id,
                    payload,
                )
            }
        )

    def delete_kachi_purchase(self, document_id: str) -> dict[str, object]:
        return self._write_call(
            lambda: {
                "kachi_purchase": self._kachi().delete_kachi_purchase(
                    self._require_context().financial_year_id,
                    document_id,
                )
            }
        )

    def lookup_kachi_sellers(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._kachi().lookup_sellers(query)})

    def lookup_kachi_items(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._kachi().lookup_items(query)})

    def lookup_kachi_rates(
        self,
        seller_party_id: str,
        commodity_id: str,
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._kachi().lookup_rates(
                    self._require_context().financial_year_id,
                    seller_party_id=seller_party_id,
                    commodity_id=commodity_id,
                )
            }
        )

    def suggest_kachi_po_no(self, entry_date: str) -> dict[str, object]:
        return self._call(
            lambda: {
                "po_no": self._kachi().suggest_po_no(
                    self._require_context().financial_year_id,
                    entry_date,
                )
            }
        )

    def get_lifting_entry(
        self,
        document_id: str = "",
        entry_date: str = "",
        challan_no: str = "",
        party_id: str = "",
    ) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "lifting_entry": self._lifting().get_lifting_entry(
                    context.financial_year_id,
                    document_id=document_id,
                    entry_date=entry_date,
                    challan_no=challan_no,
                    party_id=party_id,
                )
            }

        return self._call(action)

    def save_lifting_entry(self, payload: dict[str, Any]) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "lifting_entry": self._lifting().save_lifting_entry(
                    context.financial_year_id,
                    payload,
                )
            }

        return self._write_call(action)

    def delete_lifting_entry(self, document_id: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return {
                "lifting_entry": self._lifting().delete_lifting_entry(
                    context.financial_year_id,
                    document_id,
                )
            }

        return self._write_call(action)

    def lookup_lifting_line_parties(
        self,
        header_party_id: str,
        query: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._lifting().lookup_line_parties(
                    self._require_context().financial_year_id,
                    header_party_id=header_party_id,
                    query=query,
                )
            }
        )

    def lookup_lifting_line_items(
        self,
        line_party_id: str,
        query: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._lifting().lookup_line_items(
                    self._require_context().financial_year_id,
                    line_party_id=line_party_id,
                    query=query,
                )
            }
        )

    def lookup_lifting_line_rates(
        self,
        line_party_id: str,
        commodity_id: str,
        ref_code: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._lifting().lookup_line_rates(
                    self._require_context().financial_year_id,
                    line_party_id=line_party_id,
                    commodity_id=commodity_id,
                    ref_code=ref_code,
                )
            }
        )

    def lookup_lifting_references(
        self,
        line_party_id: str,
        commodity_id: str,
        ref_code: str,
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._lifting().lookup_purchase_references(
                    self._require_context().financial_year_id,
                    line_party_id=line_party_id,
                    commodity_id=commodity_id,
                    ref_code=ref_code,
                )
            }
        )

    def lifting_lifted_qty_summary(
        self,
        party_id: str,
        dispatch_from: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._lifting().lifted_qty_by_item(
                    self._require_context().financial_year_id,
                    party_id=party_id,
                    dispatch_from=dispatch_from,
                )
            }
        )

    def print_lifting_challans(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: self._lifting().print_lifting_challans(
                self._require_context().financial_year_id,
                party_name=str(payload.get("party_name", "")),
                from_challan=int(payload.get("from_challan", 1)),
                to_challan=int(payload.get("to_challan", 1)),
                save_pdf=bool(payload.get("save_pdf", True)),
                copy_label=str(payload.get("copy_label") or "original"),
            )
        )

    def run_report(
        self,
        report_key: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        """Run a named report from the catalog (Phases 6–7)."""
        return self._call(
            lambda: ReportCatalog(self._reports()).run(
                self._require_context().financial_year_id,
                str(report_key),
                dict(params or {}),
            )
        )

    def lookup_gst_report_items(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_reports().lookup_items(query)})

    def lookup_gst_report_item_groups(self, query: str = "") -> dict[str, object]:
        return self._call(lambda: {"rows": self._gst_reports().lookup_item_groups(query)})

    def refresh_gst_doc_issue(self, date_from: str, date_to: str) -> dict[str, object]:
        """Rebuild GSTR-1 document serial summary (doc_issue) for a period."""
        from .gst_document_issue import GstDocumentIssueService

        def action() -> dict[str, object]:
            ctx = self._require_context()
            service = GstDocumentIssueService(
                self.databases,
                str(self.databases.company_path(ctx.company_id)),
            )
            return service.refresh(ctx.financial_year_id, date_from, date_to)

        return self._call(action)

    def list_gst_doc_issue(self, date_from: str, date_to: str) -> dict[str, object]:
        """Return cached or computed doc_issue rows for GST document summary."""
        from .gst_document_issue import GstDocumentIssueService

        def action() -> dict[str, object]:
            ctx = self._require_context()
            service = GstDocumentIssueService(
                self.databases,
                str(self.databases.company_path(ctx.company_id)),
            )
            rows = service.list_rows(ctx.financial_year_id, date_from, date_to)
            return {"rows": rows}

        return self._call(action)

    def _gstr2b_service(self) -> Any:
        from .gstr2b_service import Gstr2bReconciliationService

        ctx = self._require_context()
        return Gstr2bReconciliationService(
            self.databases,
            str(self.databases.company_path(ctx.company_id)),
        )

    def select_gstr2b_json_file(self) -> dict[str, object]:
        """Open a file picker and load GSTR-2B portal JSON into memory."""

        def action() -> dict[str, object]:
            try:
                import webview
            except ImportError as exc:
                raise ValidationError("Desktop file picker is unavailable") from exc
            windows = getattr(webview, "windows", None)
            if not windows:
                raise ValidationError("Open GSTR-2B import from the desktop ERP window")
            paths = windows[0].create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("GSTR-2B JSON (*.json)", "All files (*.*)"),
            )
            if not paths:
                return {"ok": True, "cancelled": True}
            path = paths[0] if isinstance(paths, (list, tuple)) else str(paths)
            loaded = self._gstr2b_service().load_json_file(path)
            self._gstr2b_portal_records = loaded["records"]
            return {
                "ok": True,
                "cancelled": False,
                "file_path": loaded["file_path"],
                **loaded["summary"],
            }

        return self._call(action)

    def load_gstr2b_json(self, payload: dict[str, Any]) -> dict[str, object]:
        """Parse GSTR-2B JSON from ``file_path`` or ``json_text``."""

        def action() -> dict[str, object]:
            service = self._gstr2b_service()
            file_path = str(payload.get("file_path") or "").strip()
            json_text = str(payload.get("json_text") or "").strip()
            if file_path:
                loaded = service.load_json_file(file_path)
            elif json_text:
                loaded = service.load_json_text(json_text)
            else:
                raise ValidationError("file_path or json_text is required")
            self._gstr2b_portal_records = loaded["records"]
            return {"ok": True, **loaded["summary"], "file_path": file_path or None}

        return self._call(action)

    def validate_gstr1_offline_json(self, payload: dict[str, Any]) -> dict[str, object]:
        """Validate GSTR-1 JSON for GST Offline Utility Tool import."""

        def action() -> dict[str, object]:
            from .gstr1_validate import validate_gstr1_offline_utility
            import json as json_lib

            raw = payload.get("json_text")
            if not raw and payload.get("file_path"):
                raw = Path(str(payload["file_path"])).read_text(encoding="utf-8")
            if not raw:
                raise ValidationError("json_text or file_path is required")
            data = json_lib.loads(str(raw))
            return validate_gstr1_offline_utility(data)

        return self._call(action)

    def reconcile_gstr2b(self, payload: dict[str, Any]) -> dict[str, object]:
        """Match loaded GSTR-2B rows to purchase books (3-tier algorithm)."""

        def action() -> dict[str, object]:
            ctx = self._require_context()
            date_from = str(payload.get("date_from") or "").strip()
            date_to = str(payload.get("date_to") or "").strip()
            if not date_from or not date_to:
                raise ValidationError("date_from and date_to are required")
            tolerance_paise = int(payload.get("tax_tolerance_paise", 100))
            service = self._gstr2b_service()
            records = self._gstr2b_portal_records
            file_path = str(payload.get("gstr2b_file_path") or "").strip()
            if file_path:
                result = service.reconcile_from_file(
                    ctx.financial_year_id,
                    date_from,
                    date_to,
                    file_path,
                    tolerance_paise=tolerance_paise,
                )
            else:
                if not records:
                    raise ValidationError(
                        "Load GSTR-2B JSON first (select file or pass gstr2b_file_path)"
                    )
                result = service.reconcile(
                    ctx.financial_year_id,
                    date_from,
                    date_to,
                    records,
                    tolerance_paise=tolerance_paise,
                )
            display = service.display_rows(result)
            return {
                "ok": True,
                "rows": display,
                "columns": list(display[0].keys()) if display else [],
                "summary": result.get("summary"),
                "portal_summary": result.get("portal_summary"),
            }

        return self._call(action)

    def find_accounts(
        self,
        query: str = "",
        city: str = "",
        party_type: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._tools().find_accounts(
                    query=query,
                    city=city,
                    party_type=party_type,
                )
            }
        )

    def search_accounts(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._call(
            lambda: self._search_screens().search_accounts(
                self._require_context().financial_year_id,
                payload,
            )
        )

    def export_account_search(self, payload: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: self._search_screens().export_account_search(
                self._require_context().financial_year_id,
                payload,
            )
        )

    def copy_account_from_search(self, account_id: str, copy_to_name: str) -> dict[str, object]:
        return self._write_call(
            lambda: self._search_screens().copy_account(account_id, copy_to_name)
        )

    def depreciation_chart(self, round_off: bool = True) -> dict[str, object]:
        return self._call(
            lambda: {
                "rows": self._search_screens().depreciation_chart(
                    self._require_context().financial_year_id,
                    round_off=round_off,
                )
            }
        )

    def print_depreciation_chart(self, round_off: bool = True) -> dict[str, object]:
        return self._write_call(
            lambda: self._search_screens().print_depreciation_chart(
                self._require_context().financial_year_id,
                round_off=round_off,
                company_name=self._company_display_name(),
            )
        )

    def next_stock_adjustment_number(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "ref_no": self._search_screens().next_stock_adjustment_no(
                    self._require_context().financial_year_id,
                )
            }
        )

    def get_stock_adjustment_entry(
        self,
        adjustment_id: str = "",
        adjustment_date: str = "",
        ref_no: str = "",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "stock_adjustment": self._search_screens().get_stock_adjustment(
                    self._require_context().financial_year_id,
                    adjustment_id=adjustment_id,
                    adjustment_date=adjustment_date,
                    ref_no=ref_no,
                )
            }
        )

    def lookup_stock_adjustment_items(self, query: str = "") -> dict[str, object]:
        return self._call(
            lambda: {"rows": self._search_screens().lookup_stock_items(query)}
        )

    def stock_adjustment_line_hints(
        self,
        commodity_id: str,
        godown: str = "Main",
    ) -> dict[str, object]:
        return self._call(
            lambda: {
                "hints": self._search_screens().stock_line_hints(
                    self._require_context().financial_year_id,
                    commodity_id,
                    godown,
                )
            }
        )

    def save_stock_adjustment(self, payload: dict[str, Any]) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            if payload.get("lines"):
                return {
                    "stock_adjustment": self._search_screens().save_stock_adjustment(
                        context.financial_year_id,
                        payload,
                    )
                }
            return self._tools().save_stock_adjustment(
                context.financial_year_id,
                payload,
            )

        return self._write_call(action)

    def get_letterhead_print_options(self) -> dict[str, object]:
        return self._call(lambda: self._search_screens().get_letterhead_options())

    def save_letterhead_print_options(self, options: dict[str, Any]) -> dict[str, object]:
        return self._write_call(lambda: self._search_screens().save_letterhead_options(options))

    def print_company_letterhead(self) -> dict[str, object]:
        return self._write_call(
            lambda: self._search_screens().print_letterhead(self._company_display_name())
        )

    def get_company_settings(self) -> dict[str, object]:
        return self._call(
            lambda: {"settings": self._tools().get_company_settings()}
        )

    def save_company_settings(self, settings: dict[str, Any]) -> dict[str, object]:
        return self._write_call(
            lambda: self._tools().save_company_settings(settings)
        )

    def list_prefix_settings(self) -> dict[str, object]:
        return self._call(
            lambda: {
                "prefixes": self._tools().list_prefix_settings(
                    self._require_context().financial_year_id
                )
            }
        )

    def user_login_status(self) -> dict[str, object]:
        """Whether login is required and the active session snapshot."""

        def action() -> dict[str, object]:
            login_required = self._users.login_required()
            session = self._active_session_payload()
            return {
                "login_required": login_required,
                "logged_in": session is not None or not login_required,
                "session": session,
            }

        return self._call(action)

    def user_login(self, username: str, password: str) -> dict[str, object]:
        """Authenticate a catalog user for this desktop session."""

        def action() -> dict[str, object]:
            result = self._users.authenticate(username, password)
            with self._lock:
                self._session_token = str(result["token"])
            return {"session": result["user"], "expires_at": result["expires_at"]}

        return self._call(action)

    def user_logout(self) -> dict[str, object]:
        def action() -> dict[str, object]:
            with self._lock:
                token = self._session_token
                self._session_token = None
            if token:
                self._users.logout(token)
            return {"logged_out": True}

        return self._call(action)

    def user_session(self) -> dict[str, object]:
        def action() -> dict[str, object]:
            return {"session": self._active_session_payload()}

        return self._call(action)

    def list_user_permission_catalog(self) -> dict[str, object]:
        def action() -> dict[str, object]:
            current_access().assert_user_admin()
            return {"catalog": list_permission_catalog()}

        return self._call(action)

    def get_user_permissions(self, user_id: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            current_access().assert_user_admin()
            user = self._users.get_user(user_id)
            return {"user_id": user_id, "permissions": user.get("permissions") or {}}

        return self._call(action)

    def save_user_permissions(
        self,
        user_id: str,
        grants: list[dict[str, Any]],
    ) -> dict[str, object]:
        def action() -> dict[str, object]:
            current_access().assert_user_admin()
            permissions = self._users.save_permissions(user_id, grants)
            return {"user_id": user_id, "permissions": permissions}

        return self._write_call(action)

    def list_lan_users(self) -> dict[str, object]:
        """List installation users (owner admin screen)."""

        def action() -> dict[str, object]:
            current_access().assert_user_admin()
            return {"users": self._users.list_users()}

        return self._call(action)

    def save_lan_user(self, payload: dict[str, Any]) -> dict[str, object]:
        def action() -> dict[str, object]:
            if self._users.user_count() > 0:
                current_access().assert_user_admin()
            user = self._users.save_user(payload)
            grants = payload.get("permissions")
            if isinstance(grants, list):
                user["permissions"] = self._users.save_permissions(
                    str(user["user_id"]),
                    grants,
                )
            return {"user": user}

        return self._write_call(action)

    def delete_lan_user(self, user_id: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            current_access().assert_user_admin()
            self._users.delete_user(user_id)
            return {"deleted": user_id}

        return self._write_call(action)

    def set_company_profile(
        self,
        company_id: str,
        company_profile: str,
    ) -> dict[str, object]:
        """Mark a company as standard (Pakki) or kachi for visibility rules."""
        return self._write_call(
            lambda: self.databases.set_company_profile(company_id, company_profile)
        )

    def save_prefix_setting(
        self,
        document_type: str,
        prefix: str,
        next_number: int,
    ) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return self._tools().save_prefix_setting(
                context.financial_year_id,
                document_type,
                prefix,
                int(next_number),
            )

        return self._write_call(action)

    def _require_context(self) -> ActiveContext:
        """Return active context or reject calls made before startup selection."""
        with self._lock:
            if self._context is None:
                raise ValidationError("Select a company and financial year first")
            return self._context

    def _accounting(self) -> AccountingService:
        """Create an accounting service for the active company."""
        return AccountingService(self.databases, self._require_context().company_id)

    def _documents(self) -> DocumentService:
        """Create a document service for the active company."""
        return DocumentService(self.databases, self._require_context().company_id)

    def _reports(self) -> ReportService:
        """Create a report service for the active company."""
        return ReportService(self.databases, self._require_context().company_id)

    def _masters(self) -> MasterService:
        """Create a master-data service for the active company."""
        return MasterService(self.databases, self._require_context().company_id)

    def _tools(self) -> ToolsService:
        """Create tools service for the active company."""
        return ToolsService(self.databases, self._require_context().company_id)

    def _lifting(self) -> LiftingEntryService:
        return LiftingEntryService(self.databases, self._require_context().company_id)

    def _kachi(self) -> KachiPurchaseService:
        return KachiPurchaseService(self.databases, self._require_context().company_id)

    def _mandi_purchase(self) -> MandiPurchaseEntryService:
        return MandiPurchaseEntryService(self.databases, self._require_context().company_id)

    def _gst_purchase(self) -> GstPurchaseEntryService:
        return GstPurchaseEntryService(self.databases, self._require_context().company_id)

    def _invoice(self) -> InvoiceEntryService:
        return InvoiceEntryService(self.databases, self._require_context().company_id)

    def _gst_debit_note(self) -> GstDebitNoteEntryService:
        return GstDebitNoteEntryService(self.databases, self._require_context().company_id)

    def _gst_credit_note(self) -> GstCreditNoteEntryService:
        return GstCreditNoteEntryService(self.databases, self._require_context().company_id)

    def _gst_expense_voucher(self) -> GstExpenseVoucherEntryService:
        return GstExpenseVoucherEntryService(self.databases, self._require_context().company_id)

    def _debit_note(self) -> AccountingNoteEntryService:
        return AccountingNoteEntryService(
            self.databases,
            self._require_context().company_id,
            "debit_note",
        )

    def _credit_note(self) -> AccountingNoteEntryService:
        return AccountingNoteEntryService(
            self.databases,
            self._require_context().company_id,
            "credit_note",
        )

    def _voucher_entry(self) -> VoucherEntryService:
        return VoucherEntryService(self.databases, self._require_context().company_id)

    def _tds_challan(self) -> TdsChallanEntryService:
        return TdsChallanEntryService(self.databases, self._require_context().company_id)

    def _bank_reconciliation(self) -> BankReconciliationService:
        return BankReconciliationService(self.databases, self._require_context().company_id)

    def _search_screens(self) -> SearchScreensService:
        return SearchScreensService(self.databases, self._require_context().company_id)

    def _gst_reports(self) -> GstReportsService:
        return GstReportsService(self.databases, self._require_context().company_id)

    def _modern(self) -> ModernFeaturesService:
        return ModernFeaturesService(
            self.databases,
            self._require_context().company_id,
        )

    def whatsapp_for_document(self, document_id: str) -> dict[str, object]:
        return self._call(
            lambda: self._modern().whatsapp_for_document(document_id)
        )

    def whatsapp_payment_reminder(self, party_id: str) -> dict[str, object]:
        return self._call(lambda: self._modern().whatsapp_payment_reminder(party_id))

    def open_whatsapp_url(self, url: str) -> dict[str, object]:
        """Open WhatsApp share link in the system browser."""
        import webbrowser

        clean = str(url).strip()
        if not clean.startswith("https://wa.me/"):
            raise ValidationError("Invalid WhatsApp URL")
        webbrowser.open(clean)
        return {"opened": True}

    def generate_reminder_letters(self, as_of_date: str, destination: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            path = self._modern().reminder_letters_pdf(
                context.financial_year_id,
                as_of_date,
                Path(destination),
                company_name=self._company_display_name(),
            )
            return {"path": str(path)}

        return self._call(action)

    def import_bank_statement(self, source: str, dry_run: bool = True) -> dict[str, object]:
        def action() -> dict[str, object]:
            context = self._require_context()
            return self._modern().import_bank_statement(
                context.financial_year_id,
                Path(source),
                dry_run=bool(dry_run),
            )

        return self._call(action)

    def attach_document_file(self, document_id: str, source: str) -> dict[str, object]:
        return self._write_call(
            lambda: self._modern().attach_file(document_id, Path(source))
        )

    def list_document_attachments(self, document_id: str) -> dict[str, object]:
        return self._call(
            lambda: {
                "attachments": self._modern().list_attachments(document_id),
            }
        )

    def print_cover_address(self, party_id: str, destination: str) -> dict[str, object]:
        def action() -> dict[str, object]:
            path = self._modern().print_cover(
                party_id,
                Path(destination),
                company_name=self._company_display_name(),
            )
            RegisterPdfPrinter.print_path(path)
            return {"path": str(path), "submitted": True}

        return self._call(action)

    def blended_average_cost(
        self,
        commodity_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, object]:
        return self._call(
            lambda: self._modern().blended_average_cost(
                self._require_context().financial_year_id,
                commodity_id,
                date_from,
                date_to,
            )
        )

    def _company_display_name(self) -> str:
        with self.databases.connect(
            self.databases.company_path(self._require_context().company_id)
        ) as connection:
            row = connection.execute("SELECT name FROM company LIMIT 1").fetchone()
        if row is None:
            raise ValidationError("Company metadata is missing")
        return str(row["name"])

    def _active_session_payload(self) -> dict[str, object] | None:
        if not self._users.login_required():
            return None
        with self._lock:
            token = self._session_token
        if not token:
            return None
        try:
            return self._users.resolve_token(token)
        except ValidationError:
            with self._lock:
                self._session_token = None
            return None

    def _bind_session_access(self) -> None:
        if not self._users.login_required():
            bind_access(AccessPolicy.local_desktop())
            return
        session = self._active_session_payload()
        if session is None:
            bind_access(
                AccessPolicy(
                    user_id="",
                    username="",
                    role="readonly",
                    can_view_kachi=False,
                    use_custom_menu=True,
                )
            )
            return
        bind_access(AccessPolicy.from_session(session))

    def _call(self, action: Any) -> dict[str, object]:
        """Execute one API action and return a safe response envelope."""
        try:
            if self.license_service is not None:
                self.license_service.assert_session_safe()
            self._bind_session_access()
            try:
                current_access().assert_read()
                return self._result(**action())
            finally:
                clear_access_binding()
        except (AnajError, ValueError, TypeError, KeyError) as exc:
            return self._error(exc)

    def _write_call(self, action: Any) -> dict[str, object]:
        """Execute a mutation only while the signed subscription permits writes."""
        try:
            if self.license_service is not None:
                self.license_service.assert_can_write()
            self._bind_session_access()
            try:
                current_access().assert_read()
                current_access().assert_write()
                return self._result(**action())
            finally:
                clear_access_binding()
        except (AnajError, ValueError, TypeError, KeyError) as exc:
            return self._error(exc)

    @staticmethod
    def _result(**payload: object) -> dict[str, object]:
        """Create a successful API response envelope."""
        return {"ok": True, **payload}

    @staticmethod
    def _error(exc: Exception) -> dict[str, object]:
        """Create a safe error envelope without exposing internals."""
        logger.warning("Request rejected", extra={"error_type": type(exc).__name__})
        return {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
