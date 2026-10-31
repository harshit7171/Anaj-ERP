"""Read-only accounting, tax, mandi and stock report queries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .credit import CreditLimitService
from .database import DatabaseManager
from .errors import ValidationError


class ReportService:
    """Generate local report datasets from posted accounting events."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        """Resolve the company database used by report queries."""
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)

    def _modern(self) -> Any:
        from .modern_features import ModernFeaturesService

        return ModernFeaturesService(self.databases, self.company_id)

    def day_book(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        """Return posted vouchers and their debit/credit totals."""
        if date_to < date_from:
            raise ValidationError("Report end date cannot precede start date")
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    v.voucher_id, v.voucher_type, v.voucher_number,
                    v.voucher_date, v.narration,
                    SUM(vl.debit_paise) AS debit_paise,
                    SUM(vl.credit_paise) AS credit_paise
                FROM voucher v
                JOIN voucher_line vl ON vl.voucher_id = v.voucher_id
                WHERE v.financial_year_id = ?
                    AND v.status IN ('posted', 'reversed')
                    AND v.voucher_date BETWEEN ? AND ?
                GROUP BY v.voucher_id, v.voucher_type, v.voucher_number,
                    v.voucher_date, v.narration
                ORDER BY v.voucher_date, v.voucher_type, v.voucher_number
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        return [dict(row) for row in rows]

    def account_ledger(
        self,
        financial_year_id: str,
        account_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        """Return an account's opening, movements and closing balance."""
        with self.databases.connect(self.database_path) as connection:
            account = connection.execute(
                """
                SELECT name, opening_debit_paise, opening_credit_paise
                FROM account WHERE account_id = ? AND is_deleted = 0
                """,
                (account_id,),
            ).fetchone()
            if account is None:
                raise ValidationError("Account does not exist")
            previous = connection.execute(
                """
                SELECT
                    COALESCE(SUM(vl.debit_paise), 0) AS debit_paise,
                    COALESCE(SUM(vl.credit_paise), 0) AS credit_paise
                FROM voucher_line vl
                JOIN voucher v ON v.voucher_id = vl.voucher_id
                WHERE vl.account_id = ?
                    AND v.financial_year_id = ?
                    AND v.status IN ('posted', 'reversed')
                    AND v.voucher_date < ?
                """,
                (account_id, financial_year_id, date_from),
            ).fetchone()
            rows = connection.execute(
                """
                SELECT
                    v.voucher_id, v.voucher_date, v.voucher_type,
                    v.voucher_number, v.narration,
                    vl.debit_paise, vl.credit_paise
                FROM voucher_line vl
                JOIN voucher v ON v.voucher_id = vl.voucher_id
                WHERE vl.account_id = ?
                    AND v.financial_year_id = ?
                    AND v.status IN ('posted', 'reversed')
                    AND v.voucher_date BETWEEN ? AND ?
                ORDER BY v.voucher_date, v.voucher_type, v.voucher_number
                """,
                (account_id, financial_year_id, date_from, date_to),
            ).fetchall()
        opening = (
            int(account["opening_debit_paise"])
            - int(account["opening_credit_paise"])
            + int(previous["debit_paise"])
            - int(previous["credit_paise"])
        )
        running = opening
        entries: list[dict[str, Any]] = []
        for row in rows:
            running += int(row["debit_paise"]) - int(row["credit_paise"])
            entries.append({**dict(row), "running_balance_paise": running})
        return {
            "account_id": account_id,
            "account_name": account["name"],
            "opening_balance_paise": opening,
            "entries": entries,
            "closing_balance_paise": running,
        }

    def tax_register(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        tax_family: str,
    ) -> list[dict[str, Any]]:
        """Return GST, TDS or mandi charge rows by stored snapshot values."""
        families = {
            "GST": ("GST", "CGST", "SGST", "IGST"),
            "TDS": ("TDS",),
            "MANDI": ("MANDI", "APMC", "HRDF", "CESS", "MARKET"),
        }
        codes = families.get(tax_family.upper())
        if codes is None:
            raise ValidationError("Unsupported tax register")
        conditions = " OR ".join("dc.code LIKE ?" for _ in codes)
        patterns = tuple(f"{code}%" for code in codes)
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_id, d.document_type, d.document_number,
                    d.document_date, p.name AS party_name,
                    d.subtotal_paise, dc.code, dc.label, dc.rate_decimal,
                    dc.final_amount_paise, dc.is_override
                FROM document_charge dc
                JOIN document d ON d.document_id = dc.document_id
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.document_date BETWEEN ? AND ?
                    AND ({conditions})
                ORDER BY d.document_date, d.document_number, dc.line_number
                """,
                (financial_year_id, date_from, date_to, *patterns),
            ).fetchall()
        return [dict(row) for row in rows]

    def cash_book(
        self,
        financial_year_id: str,
        cash_account_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        """Return the cash ledger in receipt/payment columns."""
        ledger = self.account_ledger(
            financial_year_id,
            cash_account_id,
            date_from,
            date_to,
        )
        ledger["receipts"] = [
            entry for entry in ledger["entries"] if entry["debit_paise"] > 0
        ]
        ledger["payments"] = [
            entry for entry in ledger["entries"] if entry["credit_paise"] > 0
        ]
        return ledger

    def financial_statements(self, financial_year_id: str) -> dict[str, Any]:
        """Return trial-derived profit/loss and balance-sheet sections."""
        from .accounting import AccountingService

        company_row: Any
        with self.databases.connect(self.database_path) as connection:
            company_row = connection.execute("SELECT company_id FROM company LIMIT 1").fetchone()
        if company_row is None:
            raise ValidationError("Company metadata is missing")
        trial = AccountingService(
            self.databases,
            str(company_row["company_id"]),
        ).trial_balance(financial_year_id)
        sections: dict[str, list[dict[str, Any]]] = {
            "income": [],
            "expense": [],
            "asset": [],
            "liability": [],
            "capital": [],
        }
        for row in trial:
            account_type = str(row["account_type"])
            if account_type in sections:
                sections[account_type].append(row)
            elif account_type in {"cash", "bank", "party"}:
                target = "asset" if int(row["balance_paise"]) >= 0 else "liability"
                sections[target].append(row)
        income = -sum(
            min(int(row["balance_paise"]), 0) for row in sections["income"]
        )
        expense = sum(
            max(int(row["balance_paise"]), 0) for row in sections["expense"]
        )
        return {
            "sections": sections,
            "net_profit_paise": income - expense,
            "income_paise": income,
            "expense_paise": expense,
        }

    def document_register(
        self,
        financial_year_id: str,
        document_type: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        """Return a purchase, sale, Form-I, Form-J or challan register."""
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    d.document_id, d.document_number, d.document_date,
                    d.document_type, p.name AS party_name,
                    d.subtotal_paise, d.total_charges_paise,
                    d.total_tax_paise, d.grand_total_paise, d.status
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                    AND d.document_type = ?
                    AND d.document_date BETWEEN ? AND ?
                ORDER BY d.document_date, d.document_number
                """,
                (financial_year_id, document_type, date_from, date_to),
            ).fetchall()
        return [dict(row) for row in rows]

    def calculate_simple_interest(
        self,
        financial_year_id: str,
        account_id: str,
        date_from: str,
        date_to: str,
        annual_rate: str,
        *,
        mode: str = "simple",
    ) -> dict[str, Any]:
        """Calculate auditable vyaj (simple or compound) on debit balance."""
        from .mandi_business import calculate_vyaj_interest

        starts_on = date.fromisoformat(date_from)
        ends_on = date.fromisoformat(date_to)
        if ends_on < starts_on:
            raise ValidationError("Interest end date cannot precede start date")
        try:
            rate = Decimal(annual_rate)
        except ArithmeticError as exc:
            raise ValidationError("Interest rate is invalid") from exc
        if rate < 0:
            raise ValidationError("Interest rate cannot be negative")
        ledger = self.account_ledger(
            financial_year_id,
            account_id,
            date_from,
            date_to,
        )
        principal = max(int(ledger["closing_balance_paise"]), 0)
        days = (ends_on - starts_on).days + 1
        interest = calculate_vyaj_interest(
            principal_paise=principal,
            annual_rate_percent=rate,
            days=days,
            mode=mode,
        )
        return {
            "account_id": account_id,
            "account_name": ledger["account_name"],
            "principal_paise": principal,
            "annual_rate": str(rate),
            "days": days,
            "interest_paise": interest,
            "interest_mode": mode,
            "date_from": date_from,
            "date_to": date_to,
        }

    def compliance_status(self, financial_year_id: str) -> dict[str, Any]:
        """Return offline statutory reminders derived from local books."""
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        month_end = today.isoformat()
        tds_rows = self.tax_register(financial_year_id, month_start, month_end, "TDS")
        tds_liability_paise = sum(abs(int(row["final_amount_paise"])) for row in tds_rows)
        with self.databases.connect(self.database_path) as connection:
            year = connection.execute(
                """
                SELECT starts_on, ends_on FROM financial_year
                WHERE financial_year_id = ?
                """,
                (financial_year_id,),
            ).fetchone()
            open_eway = 0
            if year is not None:
                open_eway = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM document
                        WHERE financial_year_id = ?
                            AND status = 'posted'
                            AND eway_bill_number IS NOT NULL
                            AND trim(eway_bill_number) != ''
                            AND document_date BETWEEN ? AND ?
                        """,
                        (financial_year_id, year["starts_on"], year["ends_on"]),
                    ).fetchone()[0]
                )
        return {
            "show_tds_reminder": 1 <= today.day <= 10,
            "tds_pending_count": len(tds_rows),
            "tds_liability_paise": tds_liability_paise,
            "open_eway_bills": open_eway,
            "month_label": today.strftime("%B %Y"),
        }

    def dashboard_summary(self, financial_year_id: str) -> dict[str, Any]:
        """Aggregate local dashboard metrics for the bento workspace."""
        with self.databases.connect(self.database_path) as connection:
            inward_rows = connection.execute(
                """
                SELECT
                    substr(d.document_date, 1, 7) AS month_key,
                    COALESCE(SUM(dl.bags_scaled), 0) AS bags_scaled,
                    COALESCE(SUM(dl.quantity_scaled), 0) AS quantity_scaled
                FROM document d
                JOIN document_line dl ON dl.document_id = d.document_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.document_type IN ('inward', 'gate_pass', 'form_i_credit')
                GROUP BY substr(d.document_date, 1, 7)
                ORDER BY month_key
                """,
                (financial_year_id,),
            ).fetchall()
            company_row = connection.execute(
                "SELECT company_id FROM company LIMIT 1"
            ).fetchone()
        company_id = str(company_row["company_id"]) if company_row else ""
        credit_service = CreditLimitService(self.databases, company_id)
        farmers = credit_service.list_farmer_credit_dashboard(financial_year_id)
        risk_watchlist = [
            row for row in farmers if row["status"] in {"approaching", "exceeded"}
        ][:8]
        compliance = self.compliance_status(financial_year_id)
        today = date.today().isoformat()
        executive = self._modern().executive_metrics(financial_year_id, as_of_date=today)
        threshold_alerts = self._modern().threshold_alerts(financial_year_id)
        return {
            "inward_trends": [
                {
                    "month": str(row["month_key"]),
                    "bags_scaled": int(row["bags_scaled"]),
                    "quantity_scaled": int(row["quantity_scaled"]),
                }
                for row in inward_rows
            ],
            "farmer_risk_watchlist": risk_watchlist,
            "compliance": compliance,
            "executive": executive,
            "threshold_alerts": threshold_alerts,
        }

    def broker_commission_report(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        return self._modern().broker_commission_report(financial_year_id, date_from, date_to)

    def item_wise_profitability(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        return self._modern().item_wise_profitability(financial_year_id, date_from, date_to)

    def blended_average_cost(
        self,
        financial_year_id: str,
        commodity_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        return self._modern().blended_average_cost(
            financial_year_id,
            commodity_id,
            date_from,
            date_to,
        )

    def clause_44_export(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        return self._modern().clause_44_export(financial_year_id, date_from, date_to)

    def due_date_report(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    d.document_number, d.document_type, d.document_date, d.due_date,
                    p.name AS party_name, d.grand_total_paise, d.balance_paise
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.due_date IS NOT NULL
                    AND d.due_date BETWEEN ? AND ?
                ORDER BY d.due_date, d.document_number
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        return [dict(row) for row in rows]

    def pending_bills_report(
        self,
        financial_year_id: str,
        as_of_date: str,
    ) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    d.document_number, d.document_type, d.document_date, d.due_date,
                    p.name AS party_name, d.grand_total_paise, d.balance_paise
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.balance_paise > 0
                    AND d.document_date <= ?
                ORDER BY p.name, d.due_date
                """,
                (financial_year_id, as_of_date),
            ).fetchall()
        return [dict(row) for row in rows]

    def stock_movement_register(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        *,
        kachi_only: bool = False,
    ) -> list[dict[str, Any]]:
        type_filter = ""
        params: list[Any] = [financial_year_id, date_from, date_to]
        if kachi_only:
            type_filter = " AND d.document_type IN ('kachi_purchase')"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    im.occurred_on, c.name AS commodity_name, im.movement_type,
                    im.bags_scaled, im.quantity_scaled, d.document_number,
                    d.document_type
                FROM inventory_movement im
                JOIN commodity c ON c.commodity_id = im.commodity_id
                LEFT JOIN document d ON d.document_id = im.document_id
                WHERE im.financial_year_id = ?
                    AND im.occurred_on BETWEEN ? AND ?
                    {type_filter}
                ORDER BY im.occurred_on, c.name
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def gst_purchase_sale_summary(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        purchase_types = ("purchase_invoice", "gst_purchase", "mandi_purchase", "kachi_purchase", "form_i_credit")
        sale_types = ("sale_invoice", "form_i_debit")
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    d.document_type,
                    dc.code,
                    SUM(d.subtotal_paise) AS taxable_paise,
                    SUM(dc.final_amount_paise) AS tax_paise
                FROM document d
                JOIN document_charge dc ON dc.document_id = d.document_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.document_date BETWEEN ? AND ?
                    AND dc.is_tax = 1
                GROUP BY d.document_type, dc.code
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        purchase_tax = 0
        sale_tax = 0
        purchase_taxable = 0
        sale_taxable = 0
        detail: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            detail.append(item)
            doc_type = str(row["document_type"])
            tax = int(row["tax_paise"])
            taxable = int(row["taxable_paise"])
            if doc_type in purchase_types:
                purchase_tax += tax
                purchase_taxable += taxable
            elif doc_type in sale_types:
                sale_tax += tax
                sale_taxable += taxable
        return {
            "rows": detail,
            "purchase_taxable_paise": purchase_taxable,
            "purchase_tax_paise": purchase_tax,
            "sale_taxable_paise": sale_taxable,
            "sale_tax_paise": sale_tax,
            "net_tax_paise": sale_tax - purchase_tax,
        }

    def hsn_wise_summary(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    dl.hsn_code,
                    SUM(CASE WHEN d.document_type IN ('sale_invoice', 'form_i_debit')
                        THEN dl.amount_paise ELSE 0 END) AS sale_paise,
                    SUM(CASE WHEN d.document_type IN ('purchase_invoice', 'gst_purchase')
                        THEN dl.amount_paise ELSE 0 END) AS purchase_paise
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.document_date BETWEEN ? AND ?
                GROUP BY dl.hsn_code
                ORDER BY dl.hsn_code
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        return [dict(row) for row in rows]

    def bill_wise_gst_detail(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        side: str,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from .gst_report_filters import parse_gst_filters
        from .gst_report_filters import purchase_document_types
        from .gst_report_filters import sale_document_types

        opts = parse_gst_filters(filters or {})
        if side == "sale":
            types = sale_document_types(include_dn_cn=opts["show_dn_cn"])
        else:
            types = purchase_document_types(
                include_dn_cn=opts["show_dn_cn"],
                include_expense=opts["show_exp_detail"],
            )
        placeholders = ",".join("?" for _ in types)
        extra_sql = ""
        params: list[Any] = [financial_year_id, date_from, date_to, *types]
        if opts["commodity_id"]:
            extra_sql += " AND EXISTS (SELECT 1 FROM document_line dl WHERE dl.document_id = d.document_id AND dl.commodity_id = ?)"
            params.append(opts["commodity_id"])
        elif opts["item_query"]:
            extra_sql += (
                " AND EXISTS (SELECT 1 FROM document_line dl JOIN commodity c ON c.commodity_id = dl.commodity_id "
                "WHERE dl.document_id = d.document_id AND c.name LIKE ? COLLATE NOCASE)"
            )
            params.append(f"%{opts['item_query']}%")
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_id, d.document_type, d.document_number, d.document_date,
                    p.name AS party_name, p.gstin,
                    d.subtotal_paise AS taxable_paise, d.total_tax_paise, d.grand_total_paise
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.document_date BETWEEN ? AND ?
                    AND d.document_type IN ({placeholders})
                    {extra_sql}
                ORDER BY d.document_date, d.document_number
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def month_item_wise(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        side: str,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from .gst_report_filters import parse_gst_filters
        from .gst_report_filters import purchase_document_types
        from .gst_report_filters import sale_document_types

        opts = parse_gst_filters(filters or {})
        if side == "sale":
            types = sale_document_types(include_dn_cn=opts["show_dn_cn"])
        else:
            types = purchase_document_types(
                include_dn_cn=opts["show_dn_cn"],
                include_expense=opts["show_exp_detail"],
            )
        placeholders = ",".join("?" for _ in types)
        month_expr = "substr(d.document_date, 1, 7)"
        if opts["consolidate"]:
            month_expr = "'ALL'"
        group_col = "c.name"
        if opts["group_wise"] and opts["agricultural_group"]:
            group_col = "COALESCE(c.variety, c.name)"
        select_month = "'' AS month_key" if opts["layout_mode"] == "I" else f"{month_expr} AS month_key"
        group_by = "c.name"
        if opts["layout_mode"] == "I":
            group_by = group_col
        else:
            group_by = f"{month_expr}, {group_col}"
        extra_sql = ""
        params: list[Any] = [financial_year_id, date_from, date_to, *types]
        if opts["commodity_id"]:
            extra_sql += " AND dl.commodity_id = ?"
            params.append(opts["commodity_id"])
        elif opts["item_query"]:
            extra_sql += " AND c.name LIKE ? COLLATE NOCASE"
            params.append(f"%{opts['item_query']}%")
        if opts["agricultural_group"]:
            extra_sql += " AND COALESCE(c.variety, '') LIKE ? COLLATE NOCASE"
            params.append(f"%{opts['agricultural_group']}%")
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    {select_month},
                    {group_col} AS item_name,
                    SUM(dl.bags_scaled) AS bags,
                    SUM(dl.quantity_scaled) AS quantity_scaled,
                    SUM(dl.amount_paise) AS amount_paise
                FROM document_line dl
                JOIN document d ON d.document_id = dl.document_id
                JOIN commodity c ON c.commodity_id = dl.commodity_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.document_date BETWEEN ? AND ?
                    AND d.document_type IN ({placeholders})
                    {extra_sql}
                GROUP BY {group_by}
                ORDER BY month_key, item_name
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def gst_itc_report(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        *,
        kind: str = "availed",
    ) -> list[dict[str, Any]]:
        codes = ("ITC", "IGST", "CGST", "SGST") if kind == "availed" else ("ITC_REV", "REV")
        patterns = [f"{code}%" for code in codes]
        conditions = " OR ".join("dc.code LIKE ?" for _ in patterns)
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_date, d.document_number, d.document_type,
                    p.name AS party_name, dc.code, dc.label,
                    dc.final_amount_paise AS tax_paise
                FROM document_charge dc
                JOIN document d ON d.document_id = dc.document_id
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                  AND d.status = 'posted'
                  AND d.document_date BETWEEN ? AND ?
                  AND dc.is_tax = 1
                  AND ({conditions})
                ORDER BY d.document_date, d.document_number
                """,
                (financial_year_id, date_from, date_to, *patterns),
            ).fetchall()
            if not rows and kind == "reversed":
                rows = connection.execute(
                    """
                    SELECT
                        d.document_date, d.document_number, d.document_type,
                        p.name AS party_name, dc.code, dc.label,
                        dc.final_amount_paise AS tax_paise
                    FROM document_charge dc
                    JOIN document d ON d.document_id = dc.document_id
                    LEFT JOIN party p ON p.party_id = d.party_id
                    WHERE d.financial_year_id = ?
                      AND d.status = 'posted'
                      AND d.document_date BETWEEN ? AND ?
                      AND dc.is_tax = 1
                      AND dc.code LIKE '%ITC%'
                      AND dc.final_amount_paise < 0
                    ORDER BY d.document_date, d.document_number
                    """,
                    (financial_year_id, date_from, date_to),
                ).fetchall()
        return [dict(row) for row in rows]

    def gstr9_summary(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        summary = self.gst_purchase_sale_summary(financial_year_id, date_from, date_to)
        hsn = self.hsn_wise_summary(financial_year_id, date_from, date_to)
        return {
            "rows": summary["rows"],
            "hsn_rows": hsn,
            "net_tax_paise": summary["net_tax_paise"],
            "period_from": date_from,
            "period_to": date_to,
        }

    def gstr2b_reconciliation(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        """Purchase-side GST bills for GSTR-2B style matching (offline books)."""
        return self.bill_wise_gst_detail(
            financial_year_id,
            date_from,
            date_to,
            "purchase",
            filters={"show_dn_cn": "Y", "show_exp_detail": "Y"},
        )

    def gst_debit_credit_note_report(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        debit = self.document_register(
            financial_year_id,
            "gst_debit_note",
            date_from,
            date_to,
        )
        credit = self.document_register(
            financial_year_id,
            "gst_credit_note",
            date_from,
            date_to,
        )
        for row in debit:
            row["note_kind"] = "Debit"
        for row in credit:
            row["note_kind"] = "Credit"
        return debit + credit

    def gstr1_payload(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        *,
        validate: bool = False,
    ) -> dict[str, Any]:
        from .gstr1_export import Gstr1ExportService

        service = Gstr1ExportService(self.databases, self.database_path)
        return service.build(
            financial_year_id,
            date_from,
            date_to,
            validate=validate,
        )

    def gstr3b_summary(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        summary = self.gst_purchase_sale_summary(financial_year_id, date_from, date_to)
        outward = int(summary["sale_taxable_paise"])
        inward = int(summary["purchase_taxable_paise"])
        return {
            "table_3_1": {
                "outward_taxable_paise": outward,
                "outward_tax_paise": int(summary["sale_tax_paise"]),
                "inward_taxable_paise": inward,
                "inward_tax_paise": int(summary["purchase_tax_paise"]),
            },
            "net_tax_payable_paise": int(summary["net_tax_paise"]),
            "rows": summary["rows"],
        }

    def farmer_seasonal_turnover(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        """Farmer-wise seasonal turnover from Form-J / mandi purchase lines."""
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    p.name AS farmer_name,
                    c.name AS commodity_name,
                    strftime('%Y-%m', d.document_date) AS season_month,
                    SUM(dl.quantity_scaled) AS quantity_scaled,
                    SUM(dl.final_amount_paise) AS turnover_paise,
                    COUNT(DISTINCT d.document_id) AS document_count
                FROM document d
                JOIN document_line dl ON dl.document_id = d.document_id
                JOIN party p ON p.party_id = d.party_id
                JOIN commodity c ON c.commodity_id = dl.commodity_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.document_type IN ('form_j', 'mandi_purchase', 'kachi_purchase')
                    AND d.document_date BETWEEN ? AND ?
                GROUP BY p.party_id, c.commodity_id, season_month
                ORDER BY farmer_name, season_month, commodity_name
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        return [dict(row) for row in rows]

    def buyer_payment_aging(
        self,
        financial_year_id: str,
        as_of_date: str,
    ) -> dict[str, Any]:
        """Buyer pending balances bucketed 0–15, 16–30, 31–60, 60+ days."""
        buckets = {"0_15": 0, "16_30": 0, "31_60": 0, "60_plus": 0}
        detail: list[dict[str, Any]] = []
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    p.name AS buyer_name,
                    d.document_number,
                    d.document_date,
                    d.due_date,
                    d.balance_paise,
                    CAST(julianday(?) - julianday(COALESCE(d.due_date, d.document_date)) AS INTEGER)
                        AS age_days
                FROM document d
                JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                    AND d.status = 'posted'
                    AND d.balance_paise > 0
                    AND d.document_type IN ('sale_invoice', 'form_i_debit')
                    AND d.document_date <= ?
                ORDER BY age_days DESC, buyer_name
                """,
                (as_of_date, financial_year_id, as_of_date),
            ).fetchall()
        for row in rows:
            age = int(row["age_days"])
            amount = int(row["balance_paise"])
            if age <= 15:
                buckets["0_15"] += amount
                bucket = "0-15"
            elif age <= 30:
                buckets["16_30"] += amount
                bucket = "16-30"
            elif age <= 60:
                buckets["31_60"] += amount
                bucket = "31-60"
            else:
                buckets["60_plus"] += amount
                bucket = "60+"
            item = dict(row)
            item["aging_bucket"] = bucket
            detail.append(item)
        return {"summary_paise": buckets, "rows": detail}

    def mandi_cess_m_form(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        """Monthly mandi board cess / market fee summary (M-Form style)."""
        rows = self.tax_register(financial_year_id, date_from, date_to, "MANDI")
        by_code: dict[str, int] = {}
        for row in rows:
            code = str(row.get("tax_code") or row.get("code") or "FEE")
            by_code[code] = by_code.get(code, 0) + int(row.get("tax_amount_paise") or 0)
        return {
            "rows": rows,
            "totals_paise": by_code,
            "grand_total_paise": sum(by_code.values()),
        }

    def cash_drawer_reconciliation(
        self,
        financial_year_id: str,
        reconcile_date: str,
        cash_account_id: str,
        physical_cash_paise: int,
    ) -> dict[str, Any]:
        """Physical cash drawer vs Rokad (cash book) closing for one day."""
        book = self.cash_book(
            financial_year_id,
            cash_account_id,
            reconcile_date,
            reconcile_date,
        )
        book_balance = int(book.get("closing_balance_paise") or 0)
        variance = physical_cash_paise - book_balance
        return {
            "reconcile_date": reconcile_date,
            "physical_cash_paise": physical_cash_paise,
            "book_balance_paise": book_balance,
            "variance_paise": variance,
            "balanced": variance == 0,
            "cash_book": book,
        }

    def trial_balance_difference(self, financial_year_id: str) -> dict[str, Any]:
        from .accounting import AccountingService

        company_id = self._company_id_from_db()
        rows = AccountingService(self.databases, company_id).trial_balance(financial_year_id)
        total_debit = sum(int(row["debit_paise"]) for row in rows)
        total_credit = sum(int(row["credit_paise"]) for row in rows)
        difference = total_debit - total_credit
        return {
            "rows": rows,
            "total_debit_paise": total_debit,
            "total_credit_paise": total_credit,
            "difference_paise": difference,
        }

    def account_balances_by_group(
        self,
        financial_year_id: str,
        group_name: str = "",
    ) -> dict[str, Any]:
        import json

        from .accounting import AccountingService

        company_id = self._company_id_from_db()
        trial = AccountingService(self.databases, company_id).trial_balance(financial_year_id)
        clean_group = group_name.strip().lower()
        filtered: list[dict[str, Any]] = []
        with self.databases.connect(self.database_path) as connection:
            for row in trial:
                meta_row = connection.execute(
                    "SELECT metadata_json FROM account WHERE account_id = ?",
                    (str(row["account_id"]),),
                ).fetchone()
                meta = json.loads(str(meta_row["metadata_json"] or "{}")) if meta_row else {}
                group = str(meta.get("group_name") or row.get("account_type") or "")
                if clean_group and clean_group not in group.lower():
                    continue
                filtered.append({**dict(row), "group_name": group})
        return {"rows": filtered, "group_filter": group_name}

    def cash_in_hand_report(self, financial_year_id: str, as_of_date: str) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            accounts = connection.execute(
                """
                SELECT account_id, name FROM account
                WHERE is_deleted = 0 AND account_type = 'cash'
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        rows: list[dict[str, Any]] = []
        year_start = self._fy_start(as_of_date)
        for account in accounts:
            ledger = self.account_ledger(
                financial_year_id,
                str(account["account_id"]),
                year_start,
                as_of_date,
            )
            rows.append(
                {
                    "account_id": str(account["account_id"]),
                    "account_name": str(account["name"]),
                    "balance_paise": int(ledger["closing_balance_paise"]),
                    "balance": f"{int(ledger['closing_balance_paise']) / 100:.2f}",
                    "as_of_date": as_of_date,
                }
            )
        return {"rows": rows}

    def trading_and_balance_sheet(
        self,
        financial_year_id: str,
    ) -> dict[str, Any]:
        statement = self.financial_statements(financial_year_id)
        pl_rows = statement["sections"]["income"] + statement["sections"]["expense"]
        bs_rows = (
            statement["sections"]["asset"]
            + statement["sections"]["liability"]
            + statement["sections"]["capital"]
        )
        return {
            "profit_loss_rows": pl_rows,
            "balance_sheet_rows": bs_rows,
            "rows": [
                *[{**row, "section": "P&L"} for row in pl_rows],
                *[{**row, "section": "Balance Sheet"} for row in bs_rows],
            ],
            "net_profit_paise": statement["net_profit_paise"],
        }

    def interest_statement_rows(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        *,
        account_id: str = "",
        annual_rate: str = "18",
        mode: str = "simple",
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            if account_id.strip():
                account_ids = [account_id.strip()]
            else:
                account_ids = [
                    str(row["account_id"])
                    for row in connection.execute(
                        """
                        SELECT account_id FROM account
                        WHERE is_deleted = 0 AND account_type IN ('party', 'asset', 'liability')
                        ORDER BY name COLLATE NOCASE
                        LIMIT 200
                        """
                    ).fetchall()
                ]
        rows: list[dict[str, Any]] = []
        for aid in account_ids:
            try:
                calc = self.calculate_simple_interest(
                    financial_year_id,
                    aid,
                    date_from,
                    date_to,
                    annual_rate,
                    mode=mode,
                )
            except ValidationError:
                continue
            if int(calc["interest_paise"]) <= 0 and int(calc["principal_paise"]) <= 0:
                continue
            rows.append(
                {
                    "account_name": calc["account_name"],
                    "principal": f"{int(calc['principal_paise']) / 100:.2f}",
                    "days": calc["days"],
                    "rate": calc["annual_rate"],
                    "interest": f"{int(calc['interest_paise']) / 100:.2f}",
                    "mode": calc["interest_mode"],
                }
            )
        return {"rows": rows, "interest_mode": mode}

    def _company_id_from_db(self) -> str:
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute("SELECT company_id FROM company LIMIT 1").fetchone()
        if row is None:
            raise ValidationError("Company metadata is missing")
        return str(row["company_id"])

    @staticmethod
    def _fy_start(iso_date: str) -> str:
        parsed = date.fromisoformat(iso_date)
        year = parsed.year if parsed.month >= 4 else parsed.year - 1
        return f"{year}-04-01"
