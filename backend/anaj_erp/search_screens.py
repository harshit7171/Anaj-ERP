"""Search menu: Find Account, Depreciation Chart, Stock Adjustment, Letter Head Print."""

from __future__ import annotations

import csv
import json
import tempfile
import uuid
from decimal import Decimal
from decimal import ROUND_HALF_UP
from pathlib import Path
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .database import utc_now
from .documents import DocumentService
from .errors import ValidationError
from .register_pdf import RegisterPdfPrinter

DEFAULT_LETTERHEAD_OPTIONS: dict[str, Any] = {
    "name_source": "company_name",
    "show_address": True,
    "fields": {
        "gst_no": True,
        "pan_no": True,
        "market_license_no": True,
        "fssai_license_no": True,
        "iso_no": True,
        "iec_no": True,
        "msme": True,
        "mobile_no": True,
        "phone_no": True,
        "email": True,
        "tan_no": True,
        "cin_no": True,
        "kums_no": True,
        "rtal_no": True,
    },
}


def _round_money(paise: int, *, round_off: bool) -> str:
    if round_off:
        return f"{(paise / 100):,.0f}"
    return f"{(paise / 100):,.2f}"


class SearchScreensService:
    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.accounting = AccountingService(databases, company_id)
        self.documents = DocumentService(databases, company_id)

    def search_accounts(self, financial_year_id: str, filters: dict[str, Any]) -> dict[str, Any]:
        limit = min(max(int(filters.get("row_limit") or 100), 1), 500)
        usage = str(filters.get("usage_filter") or "all").lower()
        balances = {
            row["account_id"]: int(row["balance_paise"])
            for row in self.accounting.trial_balance(financial_year_id)
        }
        with self.databases.connect(self.database_path) as connection:
            sql = """
                SELECT
                    a.account_id,
                    a.name AS account_name,
                    a.account_type,
                    a.metadata_json,
                    p.party_id,
                    p.name AS party_name,
                    p.address,
                    p.city,
                    p.phone,
                    p.gstin,
                    p.pan AS party_pan,
                    (
                        SELECT COUNT(1) FROM voucher_line vl
                        JOIN voucher v ON v.voucher_id = vl.voucher_id
                        WHERE vl.account_id = a.account_id AND v.status = 'posted'
                    ) AS voucher_hits
                FROM account a
                LEFT JOIN party p ON p.account_id = a.account_id AND p.is_deleted = 0
                WHERE a.is_deleted = 0
            """
            params: list[Any] = []
            ac_name = str(filters.get("ac_name") or filters.get("query") or "").strip()
            if ac_name:
                sql += " AND (a.name LIKE ? COLLATE NOCASE OR p.name LIKE ? COLLATE NOCASE)"
                pattern = f"%{ac_name}%"
                params.extend([pattern, pattern])
            main_head = str(filters.get("main_head") or "").strip()
            if main_head:
                sql += " AND json_extract(COALESCE(a.metadata_json, '{}'), '$.group_name') LIKE ?"
                params.append(f"%{main_head}%")
            contact = str(filters.get("contact") or "").strip()
            if contact:
                sql += " AND json_extract(COALESCE(a.metadata_json, '{}'), '$.contact_person') LIKE ?"
                params.append(f"%{contact}%")
            city = str(filters.get("city") or "").strip()
            if city:
                sql += " AND p.city LIKE ? COLLATE NOCASE"
                params.append(f"%{city}%")
            mobile = str(filters.get("mobile") or "").strip()
            if mobile:
                sql += " AND (p.phone LIKE ? OR json_extract(COALESCE(a.metadata_json, '{}'), '$.phone') LIKE ?)"
                params.extend([f"%{mobile}%", f"%{mobile}%"])
            phone = str(filters.get("phone") or "").strip()
            if phone:
                sql += " AND (p.phone LIKE ? OR json_extract(COALESCE(a.metadata_json, '{}'), '$.phone2') LIKE ?)"
                params.extend([f"%{phone}%", f"%{phone}%"])
            gst_no = str(filters.get("gst_no") or "").strip()
            if gst_no:
                sql += " AND p.gstin LIKE ?"
                params.append(f"%{gst_no}%")
            pan_no = str(filters.get("pan_no") or "").strip()
            if pan_no:
                sql += " AND (p.pan LIKE ? OR json_extract(COALESCE(a.metadata_json, '{}'), '$.pan') LIKE ?)"
                params.extend([f"%{pan_no}%", f"%{pan_no}%"])
            lc = str(filters.get("local_central") or "N").upper()
            if lc and lc != "N":
                sql += " AND json_extract(COALESCE(a.metadata_json, '{}'), '$.local_central') = ?"
                params.append(lc)
            gst_type = str(filters.get("gst_type") or "N").upper()
            if gst_type and gst_type != "N":
                sql += " AND json_extract(COALESCE(a.metadata_json, '{}'), '$.gst_type') = ?"
                params.append(gst_type)
            sql += " ORDER BY a.name COLLATE NOCASE LIMIT ?"
            params.append(limit)
            rows = connection.execute(sql, params).fetchall()

        result_rows: list[dict[str, Any]] = []
        for row in rows:
            account_id = str(row["account_id"])
            hits = int(row["voucher_hits"] or 0)
            if usage == "used" and hits == 0:
                continue
            if usage == "unused" and hits > 0:
                continue
            meta = json.loads(str(row["metadata_json"] or "{}"))
            balance_paise = balances.get(account_id, 0)
            result_rows.append(
                {
                    "account_id": account_id,
                    "party_id": str(row["party_id"] or ""),
                    "account_name": str(row["account_name"]),
                    "head": str(meta.get("group_name") or row["account_type"]),
                    "balance": f"{balance_paise / 100:.2f}",
                    "balance_paise": balance_paise,
                    "aadhar_no": "".join(
                        filter(
                            None,
                            [
                                str(meta.get("aadhar_part1") or ""),
                                str(meta.get("aadhar_part2") or ""),
                                str(meta.get("aadhar_part3") or ""),
                            ],
                        )
                    ),
                    "ac_code": str(meta.get("account_code") or ""),
                    "bank_name": str(meta.get("bank_name") or ""),
                    "bank_ac_no": str(meta.get("bank_ac_no") or ""),
                    "ifsc_code": str(meta.get("bank_ifsc") or ""),
                    "address": str(row["address"] or meta.get("address_line2") or ""),
                    "city": str(row["city"] or ""),
                    "contact": str(meta.get("contact_person") or ""),
                    "gstin": str(row["gstin"] or ""),
                    "pan": str(row["party_pan"] or meta.get("pan") or ""),
                }
            )
        return {"rows": result_rows, "total": len(result_rows)}

    def export_account_search(self, financial_year_id: str, filters: dict[str, Any]) -> dict[str, str]:
        payload = self.search_accounts(financial_year_id, filters)
        rows = payload["rows"]
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8-sig",
            newline="",
        )
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Account Name",
                "Head",
                "Balance",
                "AcCode",
                "Bank",
                "Bank A/c",
                "IFSC",
                "Address",
                "City",
                "GSTIN",
                "PAN",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["account_name"],
                    row["head"],
                    row["balance"],
                    row["ac_code"],
                    row["bank_name"],
                    row["bank_ac_no"],
                    row["ifsc_code"],
                    row["address"],
                    row["city"],
                    row["gstin"],
                    row["pan"],
                ]
            )
        handle.close()
        return {"path": handle.name, "row_count": str(len(rows))}

    def copy_account(self, account_id: str, copy_to_name: str) -> dict[str, str]:
        target_name = str(copy_to_name or "").strip()
        if not target_name:
            raise ValidationError("Copy To name is required")
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM account WHERE account_id = ? AND is_deleted = 0",
                (account_id.strip(),),
            ).fetchone()
            if row is None:
                raise ValidationError("Account not found")
            new_id = str(uuid.uuid4())
            timestamp = utc_now()
            connection.execute(
                """
                INSERT INTO account(
                    account_id, financial_year_id, name, account_type, parent_account_id,
                    opening_debit_paise, opening_credit_paise, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
                """,
                (
                    new_id,
                    row["financial_year_id"],
                    target_name,
                    row["account_type"],
                    row["parent_account_id"],
                    row["metadata_json"],
                    timestamp,
                    timestamp,
                ),
            )
        return {"account_id": new_id, "account_name": target_name}

    def depreciation_chart(
        self,
        financial_year_id: str,
        *,
        round_off: bool = True,
    ) -> list[dict[str, Any]]:
        trial = self.accounting.trial_balance(financial_year_id)
        rows: list[dict[str, Any]] = []
        for index, row in enumerate(trial, start=1):
            meta: dict[str, Any] = {}
            with self.databases.connect(self.database_path) as connection:
                meta_row = connection.execute(
                    "SELECT metadata_json FROM account WHERE account_id = ?",
                    (str(row["account_id"]),),
                ).fetchone()
                if meta_row:
                    meta = json.loads(str(meta_row["metadata_json"] or "{}"))
            rate_text = str(meta.get("depreciation_rate") or "").strip()
            if not rate_text:
                continue
            try:
                rate = Decimal(rate_text)
            except Exception:
                continue
            if rate <= 0:
                continue
            balance_paise = max(int(row["balance_paise"]), 0)
            dep_paise = int(
                (Decimal(balance_paise) * rate / Decimal("100")).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            )
            rows.append(
                {
                    "serial_no": index,
                    "account_name": str(row["name"]),
                    "account_id": str(row["account_id"]),
                    "opening_balance": _round_money(balance_paise, round_off=round_off),
                    "depreciation_rate": str(rate),
                    "depreciation_amount": _round_money(dep_paise, round_off=round_off),
                    "closing_balance": _round_money(
                        max(balance_paise - dep_paise, 0),
                        round_off=round_off,
                    ),
                }
            )
        return rows

    def print_depreciation_chart(
        self,
        financial_year_id: str,
        *,
        round_off: bool,
        company_name: str,
    ) -> dict[str, str]:
        rows = self.depreciation_chart(financial_year_id, round_off=round_off)
        pdf_rows = [
            {
                "entry_date": str(row["serial_no"]),
                "voucher_number": row["account_name"],
                "account_name": f"Rate {row['depreciation_rate']}%",
                "debit_paise": 0,
                "credit_paise": int(
                    Decimal(str(row["depreciation_amount"]).replace(",", "")) * 100
                )
                if row["depreciation_amount"]
                else 0,
            }
            for row in rows
        ]
        destination = Path(tempfile.gettempdir()) / f"depreciation-{uuid.uuid4().hex}.pdf"
        RegisterPdfPrinter.day_book(
            company_name,
            pdf_rows,
            date_from="Depreciation Chart",
            date_to="Current FY",
            destination=destination,
        )
        RegisterPdfPrinter.print_path(destination)
        return {"path": str(destination), "row_count": str(len(rows))}

    def next_stock_adjustment_no(self, financial_year_id: str) -> str:
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT ref_no FROM stock_adjustment
                WHERE financial_year_id = ?
                ORDER BY created_at DESC LIMIT 100
                """,
                (financial_year_id,),
            ).fetchall()
        max_num = 0
        for item in row:
            digits = "".join(ch for ch in str(item["ref_no"] or "") if ch.isdigit())
            if digits:
                max_num = max(max_num, int(digits))
        return str(max_num + 1 if max_num else 1)

    def _commodity_stock(
        self,
        financial_year_id: str,
        commodity_id: str,
        godown: str,
    ) -> dict[str, int]:
        warehouse = (godown or "MAIN").strip().upper()
        if warehouse == "MAIN":
            warehouse = "MAIN"
        rows = self.documents.stock_balance(financial_year_id)
        qty = 0
        bags = 0
        for row in rows:
            if str(row["commodity_id"]) != commodity_id:
                continue
            if str(row["warehouse_code"]).upper() != warehouse:
                continue
            qty = int(row["quantity_scaled"])
            bags = int(row["bags_scaled"])
        return {"quantity_scaled": qty, "bags_scaled": bags}

    def lookup_stock_items(self, query: str = "", limit: int = 40) -> list[dict[str, Any]]:
        clean = str(query or "").strip()
        pattern = f"%{clean}%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT commodity_id, name AS item_name, variety
                FROM commodity
                WHERE is_deleted = 0
                  AND (name LIKE ? COLLATE NOCASE OR variety LIKE ? COLLATE NOCASE)
                ORDER BY name COLLATE NOCASE
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_stock_adjustment(
        self,
        financial_year_id: str,
        *,
        adjustment_id: str = "",
        adjustment_date: str = "",
        ref_no: str = "",
    ) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            row = None
            if adjustment_id.strip():
                row = connection.execute(
                    "SELECT * FROM stock_adjustment WHERE adjustment_id = ? AND financial_year_id = ?",
                    (adjustment_id.strip(), financial_year_id),
                ).fetchone()
            elif ref_no.strip() and adjustment_date.strip():
                row = connection.execute(
                    """
                    SELECT * FROM stock_adjustment
                    WHERE financial_year_id = ? AND adjustment_date = ? AND ref_no = ?
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (financial_year_id, adjustment_date.strip(), ref_no.strip()),
                ).fetchone()
            if row is None:
                raise ValidationError("Stock adjustment not found")
        meta = json.loads(str(row["lines_json"] or "{}"))
        godown = str(row["godown"] or meta.get("godown") or "Main")
        lines = meta.get("lines") if isinstance(meta.get("lines"), list) else []
        return {
            "adjustment_id": str(row["adjustment_id"]),
            "adjustment_date": str(row["adjustment_date"]),
            "ref_no": str(row["ref_no"] or ""),
            "godown": godown,
            "lines": lines,
        }

    def save_stock_adjustment(self, financial_year_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        adjustment_id = str(payload.get("adjustment_id") or "").strip()
        if adjustment_id:
            self._delete_stock_adjustment_movements(adjustment_id)
        adjustment_date = str(payload.get("adjustment_date") or "").strip()
        if not adjustment_date:
            raise ValidationError("Date is required")
        ref_no = str(payload.get("ref_no") or "").strip()
        if not ref_no:
            ref_no = self.next_stock_adjustment_no(financial_year_id)
        godown = str(payload.get("godown") or "Main").strip() or "Main"
        warehouse = godown.upper() if godown.upper() != "MAIN" else "MAIN"
        raw_lines = payload.get("lines") or []
        if not isinstance(raw_lines, list) or not raw_lines:
            raise ValidationError("At least one line is required")
        parsed_lines: list[dict[str, Any]] = []
        timestamp = utc_now()
        if not adjustment_id:
            adjustment_id = str(uuid.uuid4())
        with self.databases.connect(self.database_path) as connection:
            for raw in raw_lines:
                if not isinstance(raw, dict):
                    continue
                commodity_id = str(raw.get("commodity_id") or "").strip()
                if not commodity_id:
                    continue
                issue_qty = self._qty_scaled(raw.get("issue_qty") or raw.get("issue_wt"))
                rec_qty = self._qty_scaled(raw.get("rec_qty") or raw.get("rec_wt"))
                issue_bags = int(raw.get("issue_bags") or raw.get("issue_qty_bags") or 0)
                rec_bags = int(raw.get("rec_bags") or raw.get("rec_qty_bags") or 0)
                net_qty = rec_qty - issue_qty
                net_bags = rec_bags - issue_bags
                if net_qty == 0 and net_bags == 0:
                    continue
                stock_row = connection.execute(
                    """
                    SELECT
                        COALESCE(SUM(quantity_scaled), 0) AS quantity_scaled,
                        COALESCE(SUM(bags_scaled), 0) AS bags_scaled
                    FROM inventory_movement
                    WHERE financial_year_id = ? AND commodity_id = ?
                      AND warehouse_code = ?
                    """,
                    (financial_year_id, commodity_id, warehouse),
                ).fetchone()
                stock = {
                    "quantity_scaled": int(stock_row["quantity_scaled"]),
                    "bags_scaled": int(stock_row["bags_scaled"]),
                }
                parsed_lines.append(
                    {
                        "commodity_id": commodity_id,
                        "item_name": str(raw.get("item_name") or ""),
                        "cur_qty": stock["quantity_scaled"] / 1000,
                        "cur_wt": stock["quantity_scaled"] / 1000,
                        "issue_qty": issue_qty / 1000,
                        "issue_wt": issue_qty / 1000,
                        "rec_qty": rec_qty / 1000,
                        "rec_wt": rec_qty / 1000,
                        "remarks": str(raw.get("remarks") or ""),
                    }
                )
                movement_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO inventory_movement(
                        inventory_movement_id, financial_year_id, document_id,
                        commodity_id, warehouse_code, movement_type, quantity_scaled,
                        quantity_scale, bags_scaled, idempotency_key, occurred_on, created_at
                    ) VALUES (?, ?, NULL, ?, ?, 'stock_adjustment', ?, 3, ?, ?, ?, ?)
                    """,
                    (
                        movement_id,
                        financial_year_id,
                        commodity_id,
                        warehouse,
                        net_qty,
                        net_bags,
                        f"stock-adjustment:{adjustment_id}:{movement_id}",
                        adjustment_date,
                        timestamp,
                    ),
                )
            if not parsed_lines:
                raise ValidationError("Enter issue or receipt quantity on at least one line")
            lines_json = json.dumps({"godown": godown, "lines": parsed_lines})
            connection.execute(
                """
                INSERT INTO stock_adjustment(
                    adjustment_id, financial_year_id, adjustment_date, ref_no,
                    commodity_id, adjustment_type, bags, quantity_scaled,
                    rate_paise, amount_paise, remarks, godown, lines_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'multi', 0, 0, 0, 0, ?, ?, ?, ?, ?)
                ON CONFLICT(adjustment_id) DO UPDATE SET
                    adjustment_date = excluded.adjustment_date,
                    ref_no = excluded.ref_no,
                    godown = excluded.godown,
                    lines_json = excluded.lines_json,
                    remarks = excluded.remarks,
                    updated_at = excluded.updated_at
                """,
                (
                    adjustment_id,
                    financial_year_id,
                    adjustment_date,
                    ref_no,
                    str(parsed_lines[0]["commodity_id"]),
                    str(payload.get("header_remarks") or ""),
                    godown,
                    lines_json,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_stock_adjustment(financial_year_id, adjustment_id=adjustment_id)

    def _delete_stock_adjustment_movements(self, adjustment_id: str) -> None:
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                DELETE FROM inventory_movement
                WHERE idempotency_key LIKE ?
                """,
                (f"stock-adjustment:{adjustment_id}:%",),
            )

    def stock_line_hints(
        self,
        financial_year_id: str,
        commodity_id: str,
        godown: str,
    ) -> dict[str, str]:
        stock = self._commodity_stock(financial_year_id, commodity_id, godown)
        return {
            "cur_qty": f"{stock['quantity_scaled'] / 1000:.3f}",
            "cur_wt": f"{stock['quantity_scaled'] / 1000:.3f}",
        }

    @staticmethod
    def _qty_scaled(value: Any) -> int:
        text = str(value or "0").strip()
        if not text:
            return 0
        return int((Decimal(text) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def get_letterhead_options(self) -> dict[str, Any]:
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT settings_json FROM company_settings WHERE settings_key = 'default'"
            ).fetchone()
        settings = json.loads(str(row["settings_json"] or "{}")) if row else {}
        stored = settings.get("letterhead_print")
        if not isinstance(stored, dict):
            stored = {}
        merged = {
            **DEFAULT_LETTERHEAD_OPTIONS,
            **stored,
            "fields": {
                **DEFAULT_LETTERHEAD_OPTIONS["fields"],
                **(stored.get("fields") if isinstance(stored.get("fields"), dict) else {}),
            },
        }
        profile = self._company_profile()
        return {"options": merged, "profile": profile}

    def save_letterhead_options(self, options: dict[str, Any]) -> dict[str, Any]:
        current = self.get_letterhead_options()["options"]
        fields = options.get("fields")
        if isinstance(fields, dict):
            current["fields"] = {**current.get("fields", {}), **fields}
        for key in ("name_source", "show_address", "company_font", "address_font"):
            if key in options:
                current[key] = options[key]
        with self.databases.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT settings_json FROM company_settings WHERE settings_key = 'default'"
            ).fetchone()
            settings = json.loads(str(row["settings_json"] or "{}")) if row else {}
            settings["letterhead_print"] = current
            connection.execute(
                """
                INSERT INTO company_settings(settings_key, settings_json, updated_at)
                VALUES ('default', ?, ?)
                ON CONFLICT(settings_key) DO UPDATE SET
                    settings_json = excluded.settings_json,
                    updated_at = excluded.updated_at
                """,
                (json.dumps(settings, sort_keys=True), utc_now()),
            )
        return {"options": current}

    def print_letterhead(self, company_name: str) -> dict[str, str]:
        payload = self.get_letterhead_options()
        options = payload["options"]
        profile = payload["profile"]
        lines: list[str] = []
        if options.get("name_source") == "print_name" and profile.get("print_name"):
            lines.append(str(profile["print_name"]))
        else:
            lines.append(company_name)
        if options.get("show_address") and profile.get("address"):
            lines.append(str(profile["address"]))
        field_map = {
            "gst_no": profile.get("gstin"),
            "pan_no": profile.get("pan"),
            "market_license_no": profile.get("market_license_no"),
            "fssai_license_no": profile.get("fssai_license_no"),
            "iso_no": profile.get("iso_no"),
            "iec_no": profile.get("iec_no"),
            "msme": profile.get("msme"),
            "mobile_no": profile.get("mobile"),
            "phone_no": profile.get("phone"),
            "email": profile.get("email"),
            "tan_no": profile.get("tan_no"),
            "cin_no": profile.get("cin_no"),
            "kums_no": profile.get("kums_no"),
            "rtal_no": profile.get("rtal_no"),
        }
        labels = {
            "gst_no": "GST No",
            "pan_no": "PAN No",
            "market_license_no": "Market License No",
            "fssai_license_no": "FSSAI License No",
            "iso_no": "ISO No",
            "iec_no": "IEC No",
            "msme": "MSME",
            "mobile_no": "Mobile No",
            "phone_no": "Phone No",
            "email": "E-Mail",
            "tan_no": "TAN No",
            "cin_no": "CIN No",
            "kums_no": "KUMS No",
            "rtal_no": "RTAL No",
        }
        enabled = options.get("fields") or {}
        for key, label in labels.items():
            if not enabled.get(key):
                continue
            value = field_map.get(key)
            if value:
                lines.append(f"{label}: {value}")
        body = "\n".join(lines)
        destination = Path(tempfile.gettempdir()) / f"letterhead-{uuid.uuid4().hex}.pdf"
        RegisterPdfPrinter.day_book(
            company_name,
            [
                {
                    "entry_date": "",
                    "voucher_number": "",
                    "account_name": line,
                    "debit_paise": 0,
                    "credit_paise": 0,
                }
                for line in lines
            ]
            or [
                {
                    "entry_date": "",
                    "voucher_number": "",
                    "account_name": company_name,
                    "debit_paise": 0,
                    "credit_paise": 0,
                }
            ],
            date_from="Letter Head",
            date_to="",
            destination=destination,
        )
        RegisterPdfPrinter.print_path(destination)
        return {"path": str(destination), "preview_text": body}

    def _company_profile(self) -> dict[str, str]:
        with self.databases.connect(self.database_path) as connection:
            company = connection.execute(
                "SELECT name, legal_name, address, gstin, pan, phone FROM company LIMIT 1"
            ).fetchone()
            settings_row = connection.execute(
                "SELECT settings_json FROM company_settings WHERE settings_key = 'default'"
            ).fetchone()
        settings = json.loads(str(settings_row["settings_json"] or "{}")) if settings_row else {}
        base = dict(company) if company else {}
        profile = {
            "company_name": str(base.get("name") or ""),
            "print_name": str(settings.get("print_name") or settings.get("legal_name") or base.get("legal_name") or base.get("name") or ""),
            "address": str(base.get("address") or settings.get("address") or ""),
            "gstin": str(base.get("gstin") or settings.get("gstin") or ""),
            "pan": str(base.get("pan") or settings.get("pan") or ""),
            "phone": str(base.get("phone") or settings.get("phone") or ""),
            "mobile": str(settings.get("mobile") or settings.get("mobile_no") or ""),
            "email": str(settings.get("email") or ""),
        }
        for key in DEFAULT_LETTERHEAD_OPTIONS["fields"]:
            if key in settings:
                profile[key] = str(settings[key])
        return profile
