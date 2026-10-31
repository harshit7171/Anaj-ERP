"""Named report dispatch for Phases 6–7."""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from typing import Any

from .errors import ValidationError
from .reports import ReportService


class ReportCatalog:
    """Run report definitions by stable key."""

    def __init__(self, service: ReportService) -> None:
        self.service = service

    def run(
        self,
        financial_year_id: str,
        report_key: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        date_from = str(params.get("date_from", ""))
        date_to = str(params.get("date_to", ""))
        if report_key in {
            "cashbook",
            "ledger",
            "day_book",
            "profit_loss",
            "balance_sheet",
            "cash_in_hand",
        } and (not date_from or not date_to):
            raise ValidationError("date_from and date_to are required")

        if report_key == "trial_balance":
            from .accounting import AccountingService

            company_id = self._company_id()
            rows = AccountingService(
                self.service.databases,
                company_id,
            ).trial_balance(financial_year_id)
            return {"rows": rows}

        if report_key == "stock_balance":
            from .documents import DocumentService

            rows = DocumentService(
                self.service.databases,
                self._company_id(),
            ).stock_balance(financial_year_id)
            return {"rows": rows}

        if report_key == "day_book":
            return {"rows": self.service.day_book(financial_year_id, date_from, date_to)}

        if report_key == "cashbook":
            account_id = str(params.get("account_id", ""))
            if not account_id:
                raise ValidationError("account_id is required for cashbook")
            return {
                "cash_book": self.service.cash_book(
                    financial_year_id,
                    account_id,
                    date_from,
                    date_to,
                )
            }

        if report_key == "ledger":
            account_id = str(params.get("account_id", ""))
            if not account_id:
                raise ValidationError("account_id is required for ledger")
            return {
                "ledger": self.service.account_ledger(
                    financial_year_id,
                    account_id,
                    date_from,
                    date_to,
                )
            }

        if report_key in {"profit_loss", "balance_sheet"}:
            statement = self.service.financial_statements(financial_year_id)
            if report_key == "profit_loss":
                return {
                    "rows": statement["sections"]["income"]
                    + statement["sections"]["expense"],
                    "net_profit_paise": statement["net_profit_paise"],
                }
            return {
                "rows": statement["sections"]["asset"]
                + statement["sections"]["liability"]
                + statement["sections"]["capital"],
            }

        doc_type_map = {
            "jform_list": "form_j",
            "iform_list": "form_i_debit",
            "sale_register": "sale_invoice",
            "purchase_register": "purchase_invoice",
            "kachi_purchase_report": "kachi_purchase",
            "mandi_purchase_report": "mandi_purchase",
            "lifting_report": "lifting_entry",
            "debit_note_report": "debit_note",
            "credit_note_report": "credit_note",
        }
        if report_key in doc_type_map:
            return {
                "rows": self.service.document_register(
                    financial_year_id,
                    doc_type_map[report_key],
                    date_from,
                    date_to,
                )
            }

        if report_key == "market_fees":
            return {
                "rows": self.service.tax_register(
                    financial_year_id,
                    date_from,
                    date_to,
                    "MANDI",
                )
            }

        if report_key == "tds_report":
            return {
                "rows": self.service.tax_register(
                    financial_year_id,
                    date_from,
                    date_to,
                    "TDS",
                )
            }

        if report_key == "gst_register":
            return {
                "rows": self.service.tax_register(
                    financial_year_id,
                    date_from,
                    date_to,
                    "GST",
                )
            }

        if report_key == "due_date_report":
            return {"rows": self.service.due_date_report(financial_year_id, date_from, date_to)}

        if report_key == "pending_bills":
            return {"rows": self.service.pending_bills_report(financial_year_id, date_to)}

        if report_key == "stock_register":
            kachi = bool(params.get("kachi_only"))
            return {
                "rows": self.service.stock_movement_register(
                    financial_year_id,
                    date_from,
                    date_to,
                    kachi_only=kachi,
                )
            }

        from .gst_report_pages import GstReportPages

        gst_pages = GstReportPages(self.service)
        if report_key in GstReportPages.REPORT_KEYS:
            return gst_pages.run(report_key, financial_year_id, date_from, date_to, params)

        if report_key == "bill_wise_gst_purchase":
            return {
                "rows": self.service.bill_wise_gst_detail(
                    financial_year_id,
                    date_from,
                    date_to,
                    "purchase",
                    filters=params,
                )
            }

        if report_key == "broker_commission":
            return {
                "rows": self.service.broker_commission_report(
                    financial_year_id, date_from, date_to
                )
            }

        if report_key == "item_wise_profitability":
            return {
                "rows": self.service.item_wise_profitability(
                    financial_year_id, date_from, date_to
                )
            }


        if report_key == "blended_average_cost":
            commodity_id = str(params.get("commodity_id", "")).strip()
            if not commodity_id:
                raise ValidationError("commodity_id is required")
            return self.service.blended_average_cost(
                financial_year_id,
                commodity_id,
                date_from,
                date_to,
            )

        if report_key == "farmer_seasonal_turnover":
            return {
                "rows": self.service.farmer_seasonal_turnover(
                    financial_year_id,
                    date_from,
                    date_to,
                )
            }

        if report_key == "buyer_payment_aging":
            as_of = str(params.get("as_of_date") or date_to or date_from)
            return self.service.buyer_payment_aging(financial_year_id, as_of)

        if report_key == "mandi_cess_m_form":
            return self.service.mandi_cess_m_form(financial_year_id, date_from, date_to)

        if report_key == "cash_drawer_reconciliation":
            cash_account = str(params.get("account_id", "")).strip()
            if not cash_account:
                raise ValidationError("account_id is required")
            reconcile_date = str(params.get("reconcile_date") or date_to or date_from)
            physical = int(params.get("physical_cash_paise") or 0)
            return self.service.cash_drawer_reconciliation(
                financial_year_id,
                reconcile_date,
                cash_account,
                physical,
            )

        if report_key == "trial_balance_difference":
            return self.service.trial_balance_difference(financial_year_id)

        if report_key == "account_balances_by_group":
            return self.service.account_balances_by_group(
                financial_year_id,
                str(params.get("group_name") or ""),
            )

        if report_key == "cash_in_hand":
            as_of = str(params.get("as_of_date") or date_to or date_from or "")
            if not as_of:
                raise ValidationError("as_of_date is required")
            return self.service.cash_in_hand_report(financial_year_id, as_of)

        if report_key == "trading_pl_balance_sheet":
            return self.service.trading_and_balance_sheet(financial_year_id)

        if report_key == "interest_statement":
            if not date_from or not date_to:
                raise ValidationError("date_from and date_to are required")
            return self.service.interest_statement_rows(
                financial_year_id,
                date_from,
                date_to,
                account_id=str(params.get("account_id") or ""),
                annual_rate=str(params.get("annual_rate") or "18"),
                mode=str(params.get("interest_mode") or "simple"),
            )

        raise ValidationError(f"Unknown report key: {report_key}")

    def _company_id(self) -> str:
        with self.service.databases.connect(self.service.database_path) as connection:
            row = connection.execute("SELECT company_id FROM company LIMIT 1").fetchone()
        if row is None:
            raise ValidationError("Company metadata is missing")
        return str(row["company_id"])
