"""Mandi documents, effective-dated charges, ledger and inventory posting."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from decimal import ROUND_HALF_UP
from typing import Any

from .accounting import AccountingService
from .database import DatabaseManager
from .database import utc_now
from .domain import ChargeBasis
from .domain import ChargeMode
from .domain import ChargeRule
from .errors import CalculationError
from .errors import ValidationError
from .gst_compliance import allocate_line_taxes

PURCHASE_DOCUMENT_TYPES = {
    "purchase_invoice",
    "form_j",
    "form_i_credit",
    "purchase_memo",
    "self_purchase",
    "inward",
    "consignment_credit",
    "milling_inward",
    "kachi_purchase",
    "mandi_purchase",
    "gst_purchase",
    "gst_expense_voucher",
}
SALE_DOCUMENT_TYPES = {
    "sale_invoice",
    "form_i_debit",
    "sale_memo",
    "outward",
    "consignment_debit",
    "milling_outward",
    "gst_debit_note",
    "gst_credit_note",
}
NON_FINANCIAL_DOCUMENT_TYPES = {
    "delivery_challan",
    "transfer_challan",
    "gate_pass",
    "warehouse_transfer",
    "packing_material_transfer",
    "milling_inward",
    "milling_outward",
    "lifting_entry",
    "debit_note",
    "credit_note",
}
DOCUMENT_TYPES = PURCHASE_DOCUMENT_TYPES | SALE_DOCUMENT_TYPES | NON_FINANCIAL_DOCUMENT_TYPES
DOCUMENT_PREFIXES = {
    "form_j": "J-",
    "form_i_debit": "IS-",
    "form_i_credit": "IP-",
    "sale_invoice": "S-",
    "purchase_invoice": "P-",
    "kachi_purchase": "KP-",
    "mandi_purchase": "MP-",
    "gst_purchase": "GP-",
    "gst_debit_note": "GDN-",
    "gst_credit_note": "GCN-",
    "gst_expense_voucher": "GEV-",
    "lifting_entry": "LF-",
    "debit_note": "DN-",
    "credit_note": "CN-",
    "delivery_challan": "DC-",
    "transfer_challan": "TC-",
    "gate_pass": "GP-",
}


class DocumentService:
    """Calculate and atomically post invoices, forms and challans."""

    def __init__(self, databases: DatabaseManager, company_id: str) -> None:
        """Resolve company storage and shared accounting helpers."""
        self.databases = databases
        self.company_id = company_id
        self.database_path = databases.company_path(company_id)
        self.accounting = AccountingService(databases, company_id)

    def next_document_number(
        self,
        financial_year_id: str,
        document_type: str,
    ) -> str:
        """Return the next configured number for a document type."""
        if document_type not in DOCUMENT_TYPES:
            raise ValidationError("Unsupported document type")
        prefix = DOCUMENT_PREFIXES.get(document_type, f"{document_type[:3].upper()}-")
        with self.databases.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO numbering_series(
                    financial_year_id, document_type, prefix, next_number
                ) VALUES (?, ?, ?, 1)
                """,
                (financial_year_id, document_type, prefix),
            )
            row = connection.execute(
                """
                SELECT prefix, next_number FROM numbering_series
                WHERE financial_year_id = ? AND document_type = ?
                """,
                (financial_year_id, document_type),
            ).fetchone()
        if row is None:
            raise ValidationError("Document numbering series could not be created")
        return f"{row['prefix']}{row['next_number']}"

    def calculate(
        self,
        *,
        document_type: str,
        document_date: str,
        party_id: str | None,
        lines: list[dict[str, Any]],
        overrides: dict[str, dict[str, Any]] | None = None,
        excluded_charge_codes: list[str] | None = None,
        bonus_paise: int = 0,
        bonus_direction: str = "add",
        freight_paise: int = 0,
        freight_direction: str = "add",
    ) -> dict[str, Any]:
        """Calculate line amounts and effective charges without writing data."""
        if document_type not in DOCUMENT_TYPES:
            raise ValidationError("Unsupported document type")
        try:
            effective_date = date.fromisoformat(document_date)
        except ValueError as exc:
            raise ValidationError("Document date is invalid") from exc
        calculated_lines = [self._calculate_line(line, index) for index, line in enumerate(lines, 1)]
        if not calculated_lines:
            raise ValidationError("At least one document line is required")
        subtotal_paise = sum(int(line["amount_paise"]) for line in calculated_lines)
        total_bags = sum(
            (
                Decimal(int(line["bags_scaled"]))
                / (Decimal(10) ** int(line["bag_scale"]))
                for line in calculated_lines
            ),
            start=Decimal("0"),
        )
        total_quantity = sum(
            (
                Decimal(int(line["quantity_scaled"]))
                / (Decimal(10) ** int(line["quantity_scale"]))
                for line in calculated_lines
            ),
            start=Decimal("0"),
        )
        excluded_codes = {code.upper() for code in (excluded_charge_codes or [])}
        if "CGST" in excluded_codes and "SGST" in excluded_codes:
            excluded_codes.add("IGST")
        rules = [
            rule
            for rule in self._resolve_rules(
                document_type,
                effective_date,
                party_id,
                calculated_lines,
            )
            if str(rule["code"]).upper() not in excluded_codes
        ]
        active_tax_codes = {str(rule["code"]).upper() for rule in rules if rule["is_tax"]}
        if active_tax_codes.intersection({"CGST", "SGST"}):
            rules = [rule for rule in rules if str(rule["code"]).upper() != "IGST"]
        elif "IGST" in active_tax_codes:
            rules = [
                rule
                for rule in rules
                if str(rule["code"]).upper() not in {"CGST", "SGST"}
            ]
        if freight_paise < 0:
            raise ValidationError("Freight cannot be negative")
        if freight_direction not in {"add", "deduct"}:
            raise ValidationError("Freight direction must be add or deduct")
        signed_freight = freight_paise if freight_direction == "add" else -freight_paise
        calculated_charges: list[dict[str, Any]] = []
        overrides = overrides or {}

        def calculate_rules(
            selected_rules: list[dict[str, Any]],
            amount_base_paise: int,
        ) -> None:
            """Calculate one rule band against its correct accounting base."""
            for rule_row in selected_rules:
                rule = ChargeRule(
                    code=str(rule_row["code"]),
                    label=str(rule_row["label"]),
                    basis=ChargeBasis(str(rule_row["basis"])),
                    mode=ChargeMode(str(rule_row["mode"])),
                    rate=Decimal(str(rule_row["rate_decimal"])),
                )
                automatic = rule.calculate(
                    amount_paise=amount_base_paise,
                    bags=total_bags,
                    quantity=total_quantity,
                    weight=total_quantity,
                )
                override = overrides.get(rule.code)
                final = automatic
                reason = None
                is_override = False
                if override is not None:
                    reason = str(override.get("reason", "")).strip()
                    if not reason:
                        raise ValidationError(f"Override reason is required for {rule.code}")
                    final = int(override["amount_paise"])
                    if final < 0:
                        raise ValidationError("Override amount cannot be negative")
                    is_override = True
                signed_final = -final if rule_row["direction"] == "deduct" else final
                calculated_charges.append(
                    {
                        "charge_rule_id": rule_row["charge_rule_id"],
                        "code": rule.code,
                        "label": rule.label,
                        "basis": rule.basis.value,
                        "mode": rule.mode.value,
                        "rate_decimal": str(rule.rate),
                        "direction": rule_row["direction"],
                        "automatic_amount_paise": automatic,
                        "final_amount_paise": signed_final,
                        "is_tax": bool(rule_row["is_tax"]),
                        "is_override": is_override,
                        "override_reason": reason,
                        "ledger_account_id": rule_row["ledger_account_id"],
                    }
                )

        calculate_rules([rule for rule in rules if not rule["is_tax"]], subtotal_paise)
        non_tax_total = sum(
            int(charge["final_amount_paise"]) for charge in calculated_charges
        )
        taxable_total = subtotal_paise + non_tax_total + signed_freight
        if taxable_total < 0:
            raise CalculationError("Invoice total before tax cannot be negative")
        calculate_rules([rule for rule in rules if rule["is_tax"]], taxable_total)
        if bonus_paise < 0:
            raise ValidationError("Bonus cannot be negative")
        if bonus_direction not in {"add", "deduct"}:
            raise ValidationError("Bonus direction must be add or deduct")
        signed_bonus = bonus_paise if bonus_direction == "add" else -bonus_paise
        if bonus_paise:
            calculated_charges.append(
                {
                    "charge_rule_id": None,
                    "code": "BONUS",
                    "label": "Bonus",
                    "basis": "amount",
                    "mode": "fixed",
                    "rate_decimal": "0",
                    "direction": bonus_direction,
                    "automatic_amount_paise": bonus_paise,
                    "final_amount_paise": signed_bonus,
                    "is_tax": False,
                    "is_override": False,
                    "override_reason": None,
                    "ledger_account_id": None,
                }
            )
        total_charges = sum(
            int(charge["final_amount_paise"])
            for charge in calculated_charges
            if not charge["is_tax"] and charge["code"] != "BONUS"
        )
        total_tax = sum(
            int(charge["final_amount_paise"])
            for charge in calculated_charges
            if charge["is_tax"]
        )
        grand_total = (
            taxable_total
            + total_tax
            + signed_bonus
        )
        if grand_total < 0:
            raise CalculationError("Document grand total cannot be negative")
        commodity_flags = self._commodity_gst_flags(
            {str(line["commodity_id"]) for line in calculated_lines}
        )
        for line in calculated_lines:
            flags = commodity_flags.get(str(line["commodity_id"]), {})
            if not line.get("hsn_code") and flags.get("hsn_code"):
                line["hsn_code"] = str(flags["hsn_code"])
            if not line.get("uqc") and flags.get("uqc"):
                from .gst_compliance import normalize_uqc

                line["uqc"] = normalize_uqc(str(flags["uqc"]))
        taxed_lines = allocate_line_taxes(
            calculated_lines,
            calculated_charges,
            commodity_flags,
            signed_freight_paise=signed_freight,
        )
        return {
            "lines": taxed_lines,
            "charges": calculated_charges,
            "subtotal_paise": subtotal_paise,
            "total_charges_paise": total_charges,
            "total_tax_paise": total_tax,
            "bonus_paise": bonus_paise,
            "bonus_direction": bonus_direction,
            "signed_bonus_paise": signed_bonus,
            "freight_paise": freight_paise,
            "freight_direction": freight_direction,
            "signed_freight_paise": signed_freight,
            "taxable_total_paise": taxable_total,
            "grand_total_paise": grand_total,
            "total_bags": str(total_bags),
            "total_quantity": str(total_quantity),
        }

    def post(
        self,
        *,
        financial_year_id: str,
        document_type: str,
        document_number: str,
        document_date: str,
        party_id: str | None,
        lines: list[dict[str, Any]],
        main_account_id: str | None = None,
        party_account_id: str | None = None,
        overrides: dict[str, dict[str, Any]] | None = None,
        excluded_charge_codes: list[str] | None = None,
        bonus_paise: int = 0,
        header: dict[str, Any] | None = None,
        credit_override_confirmed: bool = False,
        manager_override_pin: str = "",
    ) -> dict[str, Any]:
        """Calculate, persist and post a document in one SQLite transaction."""
        header = header or {}
        freight_paise = int(header.get("freight_paise", 0))
        freight_direction = str(header.get("freight_direction", "add"))
        advance_cash_paise = int(header.get("advance_cash_paise", 0))
        calculation = self.calculate(
            document_type=document_type,
            document_date=document_date,
            party_id=party_id,
            lines=lines,
            overrides=overrides,
            excluded_charge_codes=excluded_charge_codes,
            bonus_paise=bonus_paise,
            bonus_direction=str(header.get("bonus_direction", "add")),
            freight_paise=freight_paise,
            freight_direction=freight_direction,
        )
        if advance_cash_paise < 0:
            raise ValidationError("Advance cash paid cannot be negative")
        if advance_cash_paise > int(calculation["grand_total_paise"]):
            raise ValidationError("Advance cash paid cannot exceed the net amount")
        if advance_cash_paise and not header.get("cash_account_id"):
            raise ValidationError("Cash account is required when advance cash is paid")
        document_id = str(uuid.uuid4())
        timestamp = utc_now()
        balance_paise = int(calculation["grand_total_paise"]) - advance_cash_paise
        with self.databases.connect(self.database_path) as connection:
            year = AccountingService._require_open_year(connection, financial_year_id)
            parsed_date = date.fromisoformat(document_date)
            from .domain import FinancialYear

            if not FinancialYear(int(year["start_year"])).contains(parsed_date):
                raise ValidationError("Document date is outside the selected financial year")
            from .access_policy import current_access
            from .mandi_business import evaluate_backdate_policy
            from .mandi_business import merge_company_settings
            from .mandi_business import verify_manager_pin

            settings_row = merge_company_settings({})
            settings_db = connection.execute(
                "SELECT settings_json FROM company_settings WHERE settings_key = 'default'"
            ).fetchone()
            if settings_db is not None:
                settings_row = merge_company_settings(
                    json.loads(str(settings_db["settings_json"] or "{}"))
                )
            evaluate_backdate_policy(
                role=current_access().role,
                voucher_date=parsed_date,
                today=date.today(),
                settings=settings_row,
            )
            if party_id:
                party = connection.execute(
                    "SELECT party_id FROM party WHERE party_id = ? AND is_deleted = 0",
                    (party_id,),
                ).fetchone()
                if party is None:
                    raise ValidationError("Party does not exist")
            is_financial = document_type not in NON_FINANCIAL_DOCUMENT_TYPES
            if is_financial and (not main_account_id or not party_account_id):
                raise ValidationError(
                    "Main and party accounts are required to post a financial document"
                )
            if (
                is_financial
                and party_id
                and document_type not in PURCHASE_DOCUMENT_TYPES
            ):
                from .credit import CreditLimitService
                from .errors import CreditLimitBreachedError

                evaluation = CreditLimitService(
                    self.databases,
                    self.company_id,
                ).evaluate_credit(
                    party_id=str(party_id),
                    financial_year_id=financial_year_id,
                    additional_debit_paise=int(calculation["grand_total_paise"]),
                    connection=connection,
                )
                if evaluation["breached"] and not credit_override_confirmed:
                    raise CreditLimitBreachedError(
                        "Credit limit breached for "
                        f"{evaluation['party_name']}: overage "
                        f"{evaluation['overage_paise']} paise"
                    )
                if evaluation["breached"] and credit_override_confirmed:
                    pin = manager_override_pin or str(header.get("manager_override_pin", ""))
                    if not verify_manager_pin(settings_row, pin):
                        raise ValidationError(
                            "Manager/Admin PIN is required to override credit limit"
                        )
            connection.execute(
                """
                INSERT INTO document(
                    document_id, financial_year_id, document_type, document_number,
                    document_date, party_id, ship_to_party_id, status,
                    reference_number, due_date, vehicle_number, driver_name,
                    gr_number, eway_bill_number, po_number, from_place, to_place,
                    remarks, dispatch_time, gr_date, freight_paise,
                    freight_direction, advance_cash_paise, balance_paise,
                    insurance_number, packing_material_transfer, stock_sale,
                    multi_tax, cash_account_id,
                    commodity_transfer_account_id, gate_pass_required,
                    self_purchase, subtotal_paise, total_charges_paise, total_tax_paise,
                    grand_total_paise, calculation_snapshot_json, header_metadata_json,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, 'posted',
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    document_id,
                    financial_year_id,
                    document_type,
                    document_number.strip(),
                    document_date,
                    party_id,
                    header.get("ship_to_party_id"),
                    header.get("reference_number"),
                    header.get("due_date"),
                    header.get("vehicle_number"),
                    header.get("driver_name"),
                    header.get("gr_number"),
                    header.get("eway_bill_number"),
                    header.get("po_number"),
                    header.get("from_place"),
                    header.get("to_place"),
                    header.get("remarks"),
                    header.get("dispatch_time"),
                    header.get("gr_date"),
                    freight_paise,
                    freight_direction,
                    advance_cash_paise,
                    balance_paise,
                    header.get("insurance_number"),
                    int(bool(header.get("packing_material_transfer"))),
                    int(bool(header.get("stock_sale"))),
                    int(bool(header.get("multi_tax"))),
                    header.get("cash_account_id"),
                    header.get("commodity_transfer_account_id"),
                    int(bool(header.get("gate_pass_required"))),
                    int(bool(header.get("self_purchase"))),
                    calculation["subtotal_paise"],
                    calculation["total_charges_paise"],
                    calculation["total_tax_paise"],
                    calculation["grand_total_paise"],
                    json.dumps(calculation, sort_keys=True),
                    json.dumps(header.get("metadata", {}), sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
            series = connection.execute(
                """
                SELECT prefix, next_number FROM numbering_series
                WHERE financial_year_id = ? AND document_type = ?
                """,
                (financial_year_id, document_type),
            ).fetchone()
            if (
                series is not None
                and document_number.strip()
                == f"{series['prefix']}{series['next_number']}"
            ):
                connection.execute(
                    """
                    UPDATE numbering_series SET next_number = next_number + 1
                    WHERE financial_year_id = ? AND document_type = ?
                    """,
                    (financial_year_id, document_type),
                )
            line_ids: list[str] = []
            for line in calculation["lines"]:
                line_id = str(uuid.uuid4())
                line_ids.append(line_id)
                connection.execute(
                    """
                    INSERT INTO document_line(
                        document_line_id, document_id, line_number, commodity_id,
                        purchaser_party_id, source_party_id, source_reference_number,
                        gate_pass_number, description, hsn_code,
                        bags_scaled, bag_scale,
                        packing_weight_scaled, loose_quantity_scaled,
                        quantity_scaled, quantity_scale, rate_paise, rate_unit,
                        amount_paise, line_metadata_json,
                        igst_paise, cgst_paise, sgst_paise, cess_paise, uqc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        line_id,
                        document_id,
                        line["line_number"],
                        line["commodity_id"],
                        line.get("purchaser_party_id"),
                        line.get("source_party_id"),
                        line.get("source_reference_number"),
                        line.get("gate_pass_number"),
                        line["description"],
                        line.get("hsn_code"),
                        line["bags_scaled"],
                        line["bag_scale"],
                        line["packing_weight_scaled"],
                        line["loose_quantity_scaled"],
                        line["quantity_scaled"],
                        line["quantity_scale"],
                        line["rate_paise"],
                        line["rate_unit"],
                        line["amount_paise"],
                        json.dumps(line.get("metadata", {}), sort_keys=True),
                        int(line.get("igst_paise", 0)),
                        int(line.get("cgst_paise", 0)),
                        int(line.get("sgst_paise", 0)),
                        int(line.get("cess_paise", 0)),
                        line.get("uqc"),
                    ),
                )
            for index, charge in enumerate(calculation["charges"], start=1):
                connection.execute(
                    """
                    INSERT INTO document_charge(
                        document_charge_id, document_id, line_number,
                        charge_rule_id, code, label, basis, rate_decimal,
                        automatic_amount_paise, final_amount_paise, is_tax,
                        is_override, override_reason, ledger_account_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        document_id,
                        index,
                        charge["charge_rule_id"],
                        charge["code"],
                        charge["label"],
                        charge["basis"],
                        charge["rate_decimal"],
                        charge["automatic_amount_paise"],
                        charge["final_amount_paise"],
                        int(charge["is_tax"]),
                        int(charge["is_override"]),
                        charge["override_reason"],
                        charge["ledger_account_id"],
                    ),
                )
            movement_sign = 1 if document_type in PURCHASE_DOCUMENT_TYPES else -1
            if document_type not in {"sale_memo", "purchase_memo", "gst_expense_voucher"}:
                self._insert_inventory(
                    connection,
                    financial_year_id,
                    document_id,
                    document_type,
                    document_date,
                    calculation["lines"],
                    line_ids,
                    movement_sign,
                    header,
                )
            bardana_type = str(header.get("bardana_type", "")).strip().lower()
            bardana_bags = int(header.get("bardana_bags", 0) or 0)
            if bardana_type in {"jute", "plastic", "hdpe"} and bardana_bags:
                movement_kind = (
                    "inward"
                    if document_type in {"inward", "gate_pass", "form_j"}
                    else "outward"
                )
                signed_bags = (
                    abs(bardana_bags)
                    if movement_kind == "inward"
                    else -abs(bardana_bags)
                )
                connection.execute(
                    """
                    INSERT INTO bardana_movement(
                        movement_id, financial_year_id, movement_type, bardana_type,
                        bags_signed, party_id, document_id, remarks, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        financial_year_id,
                        movement_kind,
                        bardana_type,
                        signed_bags,
                        party_id,
                        document_id,
                        f"Auto from {document_type} {document_number}",
                        timestamp,
                    ),
                )
            voucher_id = None
            advance_receipt_voucher_id = None
            if is_financial:
                voucher_id = self._insert_financial_posting(
                    connection,
                    financial_year_id,
                    document_id,
                    document_type,
                    document_number,
                    document_date,
                    int(calculation["grand_total_paise"]),
                    str(main_account_id),
                    str(party_account_id),
                    calculation["charges"],
                    timestamp,
                )
                connection.execute(
                    "UPDATE document SET posted_voucher_id = ? WHERE document_id = ?",
                    (voucher_id, document_id),
                )
                if advance_cash_paise:
                    advance_receipt_voucher_id = self._insert_advance_receipt(
                        connection,
                        financial_year_id,
                        document_id,
                        document_number,
                        document_date,
                        advance_cash_paise,
                        str(header["cash_account_id"]),
                        str(party_account_id),
                        timestamp,
                    )
                    connection.execute(
                        """
                        UPDATE document SET advance_receipt_voucher_id = ?
                        WHERE document_id = ?
                        """,
                        (advance_receipt_voucher_id, document_id),
                    )
                if (
                    freight_paise > 0
                    and document_type in {"delivery_challan", "gate_pass", "outward"}
                    and header.get("freight_payable_account_id")
                ):
                    self._insert_freight_payable_voucher(
                        connection,
                        financial_year_id,
                        document_id,
                        document_number,
                        document_date,
                        freight_paise,
                        str(header["freight_payable_account_id"]),
                        str(header.get("transporter_account_id") or party_account_id),
                        timestamp,
                    )
            payload = {
                "document_id": document_id,
                "financial_year_id": financial_year_id,
                "document_type": document_type,
                "document_number": document_number,
                "document_date": document_date,
                "party_id": party_id,
                "calculation": calculation,
                "header": header,
                "posted_voucher_id": voucher_id,
                "advance_receipt_voucher_id": advance_receipt_voucher_id,
            }
            self.accounting._audit(
                connection,
                financial_year_id,
                "document",
                document_id,
                "post",
                payload,
            )
        return {
            "document_id": document_id,
            "status": "posted",
            "posted_voucher_id": voucher_id,
            "advance_receipt_voucher_id": advance_receipt_voucher_id,
            **calculation,
        }

    def search_posted_documents(
        self,
        financial_year_id: str,
        document_type: str,
        query: str,
        *,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Fuzzy-friendly search for modify mode (party, village, bill no, marka)."""
        clean = " ".join(query.split()).strip()
        like = f"%{clean}%"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    d.document_id,
                    d.document_number,
                    d.document_date,
                    d.grand_total_paise,
                    d.status,
                    p.name AS party_name,
                    p.village_name,
                    d.reference_number
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                WHERE d.financial_year_id = ?
                    AND d.document_type = ?
                    AND d.status = 'posted'
                    AND (
                        ? = ''
                        OR d.document_number LIKE ? COLLATE NOCASE
                        OR d.reference_number LIKE ? COLLATE NOCASE
                        OR p.name LIKE ? COLLATE NOCASE
                        OR p.village_name LIKE ? COLLATE NOCASE
                    )
                ORDER BY d.document_date DESC, d.document_number DESC
                LIMIT ?
                """,
                (
                    financial_year_id,
                    document_type,
                    clean,
                    like,
                    like,
                    like,
                    like,
                    max(1, min(limit, 100)),
                ),
            ).fetchall()
        return [dict(row) for row in rows]

    def document_audit_trail(self, document_id: str) -> list[dict[str, Any]]:
        """Return chronological audit events for a posted document."""
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT action, reason, payload_json, occurred_at
                FROM audit_event
                WHERE entity_type = 'document' AND entity_id = ?
                ORDER BY occurred_at DESC
                """,
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, document_id: str) -> dict[str, Any]:
        """Load a complete document for preview or printing."""
        with self.databases.connect(self.database_path) as connection:
            header = connection.execute(
                """
                SELECT d.*, p.name AS party_name, p.address AS party_address,
                    p.gstin AS party_gstin, p.pan AS party_pan,
                    c.name AS company_name, c.address AS company_address,
                    c.gstin AS company_gstin, c.pan AS company_pan, c.phone
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                CROSS JOIN company c
                WHERE d.document_id = ?
                """,
                (document_id,),
            ).fetchone()
            if header is None:
                raise ValidationError("Document does not exist")
            lines = connection.execute(
                """
                SELECT dl.*, co.name AS commodity_name
                FROM document_line dl
                JOIN commodity co ON co.commodity_id = dl.commodity_id
                WHERE dl.document_id = ? ORDER BY dl.line_number
                """,
                (document_id,),
            ).fetchall()
            charges = connection.execute(
                """
                SELECT * FROM document_charge
                WHERE document_id = ? ORDER BY line_number
                """,
                (document_id,),
            ).fetchall()
        header_payload = dict(header)
        header_payload["metadata"] = json.loads(
            str(header_payload.pop("header_metadata_json", "{}"))
        )
        line_payloads = []
        for row in lines:
            payload = dict(row)
            payload["metadata"] = json.loads(
                str(payload.pop("line_metadata_json", "{}"))
            )
            line_payloads.append(payload)
        return {
            "header": header_payload,
            "lines": line_payloads,
            "charges": [dict(row) for row in charges],
        }

    def stock_balance(self, financial_year_id: str) -> list[dict[str, Any]]:
        """Return commodity balances from immutable movements."""
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    c.commodity_id,
                    c.name,
                    c.variety,
                    im.warehouse_code,
                    im.quantity_scale,
                    SUM(im.quantity_scaled) AS quantity_scaled,
                    SUM(im.bags_scaled) AS bags_scaled
                FROM inventory_movement im
                JOIN commodity c ON c.commodity_id = im.commodity_id
                WHERE im.financial_year_id = ?
                GROUP BY c.commodity_id, c.name, c.variety,
                    im.warehouse_code, im.quantity_scale
                ORDER BY c.name COLLATE NOCASE, c.variety COLLATE NOCASE
                """,
                (financial_year_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _calculate_line(line: dict[str, Any], line_number: int) -> dict[str, Any]:
        """Normalize one fixed-point document line."""
        required = ["commodity_id", "quantity_scaled", "quantity_scale", "rate_paise"]
        if any(key not in line for key in required):
            raise ValidationError("Document line is missing required values")
        quantity_scaled = int(line["quantity_scaled"])
        quantity_scale = int(line["quantity_scale"])
        rate_paise = int(line["rate_paise"])
        if quantity_scaled <= 0 or rate_paise < 0:
            raise ValidationError("Quantity must be positive and rate cannot be negative")
        if quantity_scale < 0 or quantity_scale > 6:
            raise ValidationError("Quantity scale must be between 0 and 6")
        amount = (
            Decimal(quantity_scaled)
            * Decimal(rate_paise)
            / (Decimal(10) ** quantity_scale)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        uqc = str(line.get("uqc", "")).strip() or None
        return {
            "line_number": line_number,
            "commodity_id": str(line["commodity_id"]),
            "description": str(line.get("description", "")).strip() or "Commodity",
            "purchaser_party_id": line.get("purchaser_party_id"),
            "source_party_id": line.get("source_party_id"),
            "source_reference_number": (
                str(line.get("source_reference_number", "")).strip() or None
            ),
            "gate_pass_number": str(line.get("gate_pass_number", "")).strip() or None,
            "hsn_code": str(line.get("hsn_code", "")).strip() or None,
            "bags_scaled": int(line.get("bags_scaled", 0)),
            "bag_scale": int(line.get("bag_scale", 0)),
            "packing_weight_scaled": int(line.get("packing_weight_scaled", 0)),
            "loose_quantity_scaled": int(line.get("loose_quantity_scaled", 0)),
            "quantity_scaled": quantity_scaled,
            "quantity_scale": quantity_scale,
            "rate_paise": rate_paise,
            "rate_unit": str(line.get("rate_unit", "unit")),
            "amount_paise": int(amount),
            "uqc": uqc,
            "metadata": dict(line.get("metadata") or {}),
        }

    def _commodity_gst_flags(self, commodity_ids: set[str]) -> dict[str, dict[str, Any]]:
        if not commodity_ids:
            return {}
        placeholders = ",".join("?" for _ in commodity_ids)
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT commodity_id, hsn_code, uqc, item_metadata_json
                FROM commodity
                WHERE commodity_id IN ({placeholders}) AND is_deleted = 0
                """,
                tuple(commodity_ids),
            ).fetchall()
        flags: dict[str, dict[str, Any]] = {}
        for row in rows:
            meta = json.loads(str(row["item_metadata_json"] or "{}"))
            flags[str(row["commodity_id"])] = {
                "hsn_code": row["hsn_code"],
                "uqc": row["uqc"] or meta.get("uqc"),
                "exempted": meta.get("exempted"),
                "blocked_itc": meta.get("blocked_itc"),
                "rcm_purchase": meta.get("rcm_purchase"),
            }
        return flags

    def _resolve_rules(
        self,
        document_type: str,
        effective_date: date,
        party_id: str | None,
        lines: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Resolve the most-specific effective rule for each charge code."""
        commodity_ids = {str(line["commodity_id"]) for line in lines}
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM charge_rule
                WHERE transaction_type = ?
                    AND effective_from <= ?
                    AND (effective_to IS NULL OR effective_to >= ?)
                    AND is_deleted = 0
                    AND (party_id IS NULL OR party_id = ?)
                ORDER BY priority, code, effective_from DESC, created_at DESC
                """,
                (
                    document_type,
                    effective_date.isoformat(),
                    effective_date.isoformat(),
                    party_id,
                ),
            ).fetchall()
        candidates = [
            dict(row)
            for row in rows
            if row["commodity_id"] is None or str(row["commodity_id"]) in commodity_ids
        ]
        selected: dict[str, dict[str, Any]] = {}
        for row in candidates:
            specificity = int(row["party_id"] is not None) + int(
                row["commodity_id"] is not None
            )
            previous = selected.get(str(row["code"]))
            if previous is None or specificity > int(previous["_specificity"]):
                row["_specificity"] = specificity
                selected[str(row["code"])] = row
        for row in selected.values():
            row.pop("_specificity", None)
        return sorted(selected.values(), key=lambda row: (row["priority"], row["code"]))

    @staticmethod
    def _insert_inventory(
        connection: Any,
        financial_year_id: str,
        document_id: str,
        document_type: str,
        document_date: str,
        lines: list[dict[str, Any]],
        line_ids: list[str],
        sign: int,
        header: dict[str, Any],
    ) -> None:
        """Create idempotent stock movements for each document line."""
        fields = (header.get("metadata") or {}).get("fields") or {}
        source_warehouse = str(fields.get("fromGodown") or "MAIN").strip() or "MAIN"
        target_warehouse = str(fields.get("toGodown") or "MAIN").strip() or "MAIN"
        if document_type == "transfer_challan" and source_warehouse == target_warehouse:
            raise ValidationError("Source and destination godowns must be different")
        for line, line_id in zip(lines, line_ids, strict=True):
            line_sign = sign
            direction = str((line.get("metadata") or {}).get("inventory_direction", ""))
            if direction == "in":
                line_sign = 1
            elif direction == "out":
                line_sign = -1
            movements = [(document_type, "MAIN", line_sign, "stock")]
            if document_type == "transfer_challan":
                movements = [
                    ("transfer_out", source_warehouse, -1, "stock-out"),
                    ("transfer_in", target_warehouse, 1, "stock-in"),
                ]
            for movement_type, warehouse, movement_sign, suffix in movements:
                connection.execute(
                    """
                    INSERT INTO inventory_movement(
                        inventory_movement_id, financial_year_id, document_id,
                        document_line_id, commodity_id, warehouse_code, movement_type,
                        quantity_scaled, quantity_scale, bags_scaled,
                        idempotency_key, occurred_on, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        financial_year_id,
                        document_id,
                        line_id,
                        line["commodity_id"],
                        warehouse,
                        movement_type,
                        movement_sign * int(line["quantity_scaled"]),
                        line["quantity_scale"],
                        movement_sign * int(line["bags_scaled"]),
                        f"{document_id}:{line_id}:{suffix}",
                        document_date,
                        utc_now(),
                    ),
                )

    @staticmethod
    def _insert_freight_payable_voucher(
        connection: Any,
        financial_year_id: str,
        document_id: str,
        document_number: str,
        document_date: str,
        freight_paise: int,
        expense_account_id: str,
        transporter_account_id: str,
        timestamp: str,
    ) -> str:
        """Create truck/cartage payable for dispatch documents."""
        voucher_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO voucher(
                voucher_id, financial_year_id, voucher_type, voucher_number,
                voucher_date, narration, status, created_at, updated_at
            ) VALUES (?, ?, 'freight', ?, ?, ?, 'posted', ?, ?)
            """,
            (
                voucher_id,
                financial_year_id,
                f"FR-{document_number}",
                document_date,
                f"Freight for dispatch {document_number}",
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO voucher_line(
                voucher_line_id, voucher_id, account_id, line_number,
                debit_paise, credit_paise, narration
            ) VALUES (?, ?, ?, 1, ?, 0, ?)
            """,
            (
                str(uuid.uuid4()),
                voucher_id,
                expense_account_id,
                freight_paise,
                document_id,
            ),
        )
        connection.execute(
            """
            INSERT INTO voucher_line(
                voucher_line_id, voucher_id, account_id, line_number,
                debit_paise, credit_paise, narration
            ) VALUES (?, ?, ?, 2, 0, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                voucher_id,
                transporter_account_id,
                freight_paise,
                document_id,
            ),
        )
        return voucher_id

    @staticmethod
    def _insert_advance_receipt(
        connection: Any,
        financial_year_id: str,
        document_id: str,
        document_number: str,
        document_date: str,
        amount_paise: int,
        cash_account_id: str,
        party_account_id: str,
        timestamp: str,
    ) -> str:
        """Post buyer cash received with the invoice in the same transaction."""
        account_count = connection.execute(
            """
            SELECT COUNT(*) FROM account
            WHERE account_id IN (?, ?) AND is_deleted = 0
            """,
            (cash_account_id, party_account_id),
        ).fetchone()[0]
        if account_count != 2 or cash_account_id == party_account_id:
            raise ValidationError("Advance receipt contains an invalid cash account")
        voucher_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO voucher(
                voucher_id, financial_year_id, voucher_type, voucher_number,
                voucher_date, narration, status, created_at, updated_at
            ) VALUES (?, ?, 'receipt', ?, ?, ?, 'posted', ?, ?)
            """,
            (
                voucher_id,
                financial_year_id,
                f"ADV-{document_number}",
                document_date,
                f"Advance cash received against invoice {document_number}",
                timestamp,
                timestamp,
            ),
        )
        for line_number, account_id, debit, credit in (
            (1, cash_account_id, amount_paise, 0),
            (2, party_account_id, 0, amount_paise),
        ):
            connection.execute(
                """
                INSERT INTO voucher_line(
                    voucher_line_id, voucher_id, account_id, line_number,
                    debit_paise, credit_paise, narration
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    voucher_id,
                    account_id,
                    line_number,
                    debit,
                    credit,
                    document_id,
                ),
            )
        return voucher_id

    @staticmethod
    def _insert_financial_posting(
        connection: Any,
        financial_year_id: str,
        document_id: str,
        document_type: str,
        document_number: str,
        document_date: str,
        grand_total_paise: int,
        main_account_id: str,
        party_account_id: str,
        charges: list[dict[str, Any]],
        timestamp: str,
    ) -> str:
        """Insert a balanced summary posting for a financial document."""
        account_ids = {main_account_id, party_account_id}
        account_ids.update(
            str(charge["ledger_account_id"])
            for charge in charges
            if charge["ledger_account_id"]
        )
        placeholders = ",".join("?" for _ in account_ids)
        count = connection.execute(
            f"""
            SELECT COUNT(*) FROM account
            WHERE account_id IN ({placeholders}) AND is_deleted = 0
            """,
            tuple(account_ids),
        ).fetchone()[0]
        if count != len(account_ids):
            raise ValidationError("Document posting contains an invalid account")
        voucher_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO voucher(
                voucher_id, financial_year_id, voucher_type, voucher_number,
                voucher_date, narration, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'posted', ?, ?)
            """,
            (
                voucher_id,
                financial_year_id,
                document_type,
                document_number,
                document_date,
                f"Posted from {document_type} {document_number}",
                timestamp,
                timestamp,
            ),
        )
        purchase = document_type in PURCHASE_DOCUMENT_TYPES
        ledger_totals: dict[str, int] = {main_account_id: grand_total_paise}
        for charge in charges:
            ledger_account_id = charge["ledger_account_id"]
            if not ledger_account_id:
                continue
            amount = int(charge["final_amount_paise"])
            ledger_totals[main_account_id] -= amount
            ledger_totals[str(ledger_account_id)] = (
                ledger_totals.get(str(ledger_account_id), 0) + amount
            )
        entries: list[tuple[str, int, int]] = []
        if purchase:
            entries.append((party_account_id, 0, grand_total_paise))
            entries.extend(
                (
                    account_id,
                    max(amount, 0),
                    max(-amount, 0),
                )
                for account_id, amount in ledger_totals.items()
            )
        else:
            entries.append((party_account_id, grand_total_paise, 0))
            entries.extend(
                (
                    account_id,
                    max(-amount, 0),
                    max(amount, 0),
                )
                for account_id, amount in ledger_totals.items()
            )
        debit = sum(entry[1] for entry in entries)
        credit = sum(entry[2] for entry in entries)
        if debit != credit:
            raise CalculationError("Generated document posting is not balanced")
        for index, (account_id, debit_paise, credit_paise) in enumerate(entries, start=1):
            if debit_paise == 0 and credit_paise == 0:
                continue
            connection.execute(
                """
                INSERT INTO voucher_line(
                    voucher_line_id, voucher_id, account_id, line_number,
                    debit_paise, credit_paise, narration
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    voucher_id,
                    account_id,
                    index,
                    debit_paise,
                    credit_paise,
                    document_id,
                ),
            )
        return voucher_id
