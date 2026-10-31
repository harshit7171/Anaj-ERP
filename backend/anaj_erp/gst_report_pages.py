"""GST menu reports — display-ready rows, columns, footers, and section layouts."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from .errors import ValidationError
from .gst_report_filters import parse_gst_filters
from .gst_report_filters import period_from_return_month
from .gst_report_filters import purchase_document_types
from .gst_report_filters import sale_document_types
from .hsn_apportionment import build_hsn_summary_from_documents
from .hsn_apportionment import load_apportioned_documents_for_period
from .reports import ReportService

TAX_AGG_SQL = """
LEFT JOIN (
    SELECT
        document_id,
        SUM(CASE WHEN code LIKE 'CGST%' THEN final_amount_paise ELSE 0 END) AS cgst_paise,
        SUM(CASE WHEN code LIKE 'SGST%' THEN final_amount_paise ELSE 0 END) AS sgst_paise,
        SUM(CASE WHEN code LIKE 'IGST%' THEN final_amount_paise ELSE 0 END) AS igst_paise,
        SUM(CASE WHEN code LIKE '%CESS%' THEN final_amount_paise ELSE 0 END) AS cess_paise
    FROM document_charge
    WHERE is_tax = 1
    GROUP BY document_id
) tax ON tax.document_id = d.document_id
"""


def _rupees(paise: int) -> str:
    return f"{Decimal(int(paise)) / Decimal(100):.2f}"


def _side_label(document_type: str, purchase_types: tuple[str, ...], sale_types: tuple[str, ...]) -> str:
    if document_type in purchase_types:
        return "Purchase"
    if document_type in sale_types:
        return "Sale"
    return document_type.replace("_", " ").title()


class GstReportPages:
    """Build GST report payloads matching legacy menu column layouts."""

    REPORT_KEYS = frozenset(
        {
            "gst_purchase_sale_summary",
            "bill_wise_gst_sale",
            "month_item_wise_sale",
            "month_item_wise_purchase",
            "gst_purchase_detail",
            "gstr1_json",
            "gst_dn_cn_report",
            "hsn_wise_summary",
            "gstr3b_summary",
            "gstr2b_report",
            "itc_reversed_report",
            "itc_availed_report",
            "gstr9_report",
            "clause_44_tax_audit",
        }
    )

    def __init__(self, service: ReportService) -> None:
        self.service = service
        self.databases = service.databases
        self.database_path = service.database_path

    def run(
        self,
        report_key: str,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if report_key not in self.REPORT_KEYS:
            raise ValidationError(f"Unknown GST page report: {report_key}")
        date_from, date_to = period_from_return_month(params, date_from, date_to)
        return self._dispatch(report_key, financial_year_id, date_from, date_to, params)

    def _dispatch(
        self,
        report_key: str,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if report_key == "gst_purchase_sale_summary":
            return self.purchase_sale_summary(financial_year_id, date_from, date_to, params)
        if report_key == "bill_wise_gst_sale":
            return self.bill_wise_sale_detail(financial_year_id, date_from, date_to, params)
        if report_key == "month_item_wise_sale":
            return self.month_item_wise(financial_year_id, date_from, date_to, "sale", params)
        if report_key == "month_item_wise_purchase":
            return self.month_item_wise(financial_year_id, date_from, date_to, "purchase", params)
        if report_key == "gst_purchase_detail":
            return self.gst_purchase_detail(financial_year_id, date_from, date_to, params)
        if report_key == "gstr1_json":
            return self.gstr1(financial_year_id, date_from, date_to, params)
        if report_key == "gst_dn_cn_report":
            return self.debit_credit_notes(financial_year_id, date_from, date_to, params)
        if report_key == "hsn_wise_summary":
            return self.hsn_wise(financial_year_id, date_from, date_to, params)
        if report_key == "gstr3b_summary":
            return self.gstr3b(financial_year_id, date_from, date_to)
        if report_key == "gstr2b_report":
            return self.gstr2b(financial_year_id, date_from, date_to, params)
        if report_key == "itc_reversed_report":
            return self.itc_reversed_claimed(financial_year_id, date_from, date_to, params)
        if report_key == "itc_availed_report":
            return self.itc_availed(financial_year_id, date_from, date_to, params)
        if report_key == "gstr9_report":
            return self.gstr9(financial_year_id, date_from, date_to)
        if report_key == "clause_44_tax_audit":
            return self.clause_44(financial_year_id, date_from, date_to)
        raise ValidationError(f"Unknown GST page report: {report_key}")

    def purchase_sale_summary(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        opts = parse_gst_filters(params)
        purchase_types = purchase_document_types(include_dn_cn=opts["show_dn_cn"], include_expense=True)
        sale_types = sale_document_types(include_dn_cn=opts["show_dn_cn"])
        all_types = tuple(dict.fromkeys((*purchase_types, *sale_types)))
        placeholders = ",".join("?" for _ in all_types)
        extra = ""
        sql_params: list[Any] = [financial_year_id, date_from, date_to, *all_types]
        if opts["party_id"]:
            extra += " AND d.party_id = ?"
            sql_params.append(opts["party_id"])
        if opts["transaction_type"] == "purchase":
            extra += f" AND d.document_type IN ({','.join('?' for _ in purchase_types)})"
            sql_params.extend(purchase_types)
        elif opts["transaction_type"] == "sale":
            extra += f" AND d.document_type IN ({','.join('?' for _ in sale_types)})"
            sql_params.extend(sale_types)
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_date,
                    d.document_number,
                    COALESCE(p.name, '') AS party_name,
                    d.document_type,
                    d.subtotal_paise AS taxable_paise,
                    COALESCE(tax.cgst_paise, 0) AS cgst_paise,
                    COALESCE(tax.sgst_paise, 0) AS sgst_paise,
                    COALESCE(tax.igst_paise, 0) AS igst_paise,
                    d.grand_total_paise
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                {TAX_AGG_SQL}
                WHERE d.financial_year_id = ?
                  AND d.status = 'posted'
                  AND d.document_date BETWEEN ? AND ?
                  AND d.document_type IN ({placeholders})
                  {extra}
                ORDER BY d.document_date, d.document_number
                """,
                sql_params,
            ).fetchall()
        display: list[dict[str, str]] = []
        sum_taxable = sum_cgst = sum_sgst = sum_igst = sum_total = 0
        for row in rows:
            taxable = int(row["taxable_paise"])
            cgst = int(row["cgst_paise"])
            sgst = int(row["sgst_paise"])
            igst = int(row["igst_paise"])
            total = int(row["grand_total_paise"])
            sum_taxable += taxable
            sum_cgst += cgst
            sum_sgst += sgst
            sum_igst += igst
            sum_total += total
            display.append(
                {
                    "Date": str(row["document_date"]),
                    "Voucher/Invoice No": str(row["document_number"]),
                    "Party Name": str(row["party_name"]),
                    "Transaction Type": _side_label(str(row["document_type"]), purchase_types, sale_types),
                    "Taxable Amount": _rupees(taxable),
                    "CGST": _rupees(cgst),
                    "SGST": _rupees(sgst),
                    "IGST": _rupees(igst),
                    "Total Amount": _rupees(total),
                }
            )
        sum_taxes = sum_cgst + sum_sgst + sum_igst
        return {
            "rows": display,
            "columns": [
                "Date",
                "Voucher/Invoice No",
                "Party Name",
                "Transaction Type",
                "Taxable Amount",
                "CGST",
                "SGST",
                "IGST",
                "Total Amount",
            ],
            "footer": {
                "Taxable Amount": _rupees(sum_taxable),
                "Taxes": _rupees(sum_taxes),
                "Grand Total": _rupees(sum_total),
            },
        }

    def bill_wise_sale_detail(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        opts = parse_gst_filters(params)
        types = sale_document_types(include_dn_cn=opts["show_dn_cn"])
        placeholders = ",".join("?" for _ in types)
        extra = ""
        sql_params: list[Any] = [financial_year_id, date_from, date_to, *types]
        if opts["party_id"]:
            extra += " AND d.party_id = ?"
            sql_params.append(opts["party_id"])
        if opts["gstin_query"]:
            extra += " AND COALESCE(p.gstin, '') LIKE ?"
            sql_params.append(f"%{opts['gstin_query']}%")
        if opts["b2b_b2c"] == "b2b":
            extra += " AND COALESCE(p.gstin, '') != '' AND length(trim(p.gstin)) = 15"
        elif opts["b2b_b2c"] == "b2c":
            extra += " AND (p.gstin IS NULL OR length(trim(p.gstin)) != 15)"
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_date,
                    d.document_number,
                    COALESCE(p.name, '') AS customer_name,
                    COALESCE(p.gstin, '') AS gstin,
                    COALESCE(p.state_code, '') AS state_pos,
                    COALESCE(dl.hsn_code, c.hsn_code, '') AS hsn_code,
                    dl.amount_paise AS line_taxable_paise,
                    COALESCE(tax.cgst_paise, 0) AS doc_cgst_paise,
                    COALESCE(tax.sgst_paise, 0) AS doc_sgst_paise,
                    COALESCE(tax.igst_paise, 0) AS doc_igst_paise,
                    COALESCE(tax.cess_paise, 0) AS doc_cess_paise,
                    d.grand_total_paise,
                    d.document_id
                FROM document d
                JOIN document_line dl ON dl.document_id = d.document_id
                JOIN commodity c ON c.commodity_id = dl.commodity_id
                LEFT JOIN party p ON p.party_id = d.party_id
                {TAX_AGG_SQL}
                WHERE d.financial_year_id = ?
                  AND d.status = 'posted'
                  AND d.document_date BETWEEN ? AND ?
                  AND d.document_type IN ({placeholders})
                  {extra}
                ORDER BY d.document_date, d.document_number, dl.line_number
                """,
                sql_params,
            ).fetchall()
        display: list[dict[str, str]] = []
        for row in rows:
            line_taxable = int(row["line_taxable_paise"])
            display.append(
                {
                    "Invoice Date": str(row["document_date"]),
                    "Invoice No": str(row["document_number"]),
                    "Customer Name": str(row["customer_name"]),
                    "GSTIN": str(row["gstin"]),
                    "State POS (Place of Supply)": str(row["state_pos"]),
                    "HSN Code": str(row["hsn_code"]),
                    "Taxable Value": _rupees(line_taxable),
                    "CGST": _rupees(int(row["doc_cgst_paise"])),
                    "SGST": _rupees(int(row["doc_sgst_paise"])),
                    "IGST": _rupees(int(row["doc_igst_paise"])),
                    "Cess": _rupees(int(row["doc_cess_paise"])),
                    "Total Invoice Value": _rupees(int(row["grand_total_paise"])),
                }
            )
        columns = [
            "Invoice Date",
            "Invoice No",
            "Customer Name",
            "GSTIN",
            "State POS (Place of Supply)",
            "HSN Code",
            "Taxable Value",
            "CGST",
            "SGST",
            "IGST",
            "Cess",
            "Total Invoice Value",
        ]
        return {"rows": display, "columns": columns}

    def month_item_wise(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        side: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        raw = self.service.month_item_wise(financial_year_id, date_from, date_to, side, filters=params)
        opts = parse_gst_filters(params)
        show_exp = opts["show_exp_detail"]
        is_sale = side == "sale"
        display: list[dict[str, str]] = []
        for row in raw:
            month_key = str(row.get("month_key") or "")
            period = "Consolidated" if opts["consolidate"] else (month_key or "—")
            qty = Decimal(str(row.get("quantity_scaled") or 0)) / Decimal(1000)
            amount = int(row.get("amount_paise") or 0)
            rate = Decimal(amount) / Decimal(100) / qty if qty else Decimal(0)
            item: dict[str, str] = {
                "Month/Period": period,
                "Item Name": str(row.get("item_name") or ""),
                "Quantity (Quintals)": f"{qty:.3f}",
                "Rate": f"{rate:.2f}",
                "Gross Value": _rupees(amount),
            }
            if show_exp:
                item["Freight/Expenses"] = _rupees(0)
            item["Net Value"] = _rupees(amount)
            if not is_sale:
                item = {
                    "Month/Period": period,
                    "Item Name": str(row.get("item_name") or ""),
                    "Purchased Qty": f"{qty:.3f}",
                    "Average Rate": f"{rate:.2f}",
                    "Taxable Value": _rupees(amount),
                    "Associated Taxes": _rupees(0),
                    "Net Purchase Value": _rupees(amount),
                }
            display.append(item)
        if is_sale:
            columns = ["Month/Period", "Item Name", "Quantity (Quintals)", "Rate", "Gross Value"]
            if show_exp:
                columns.append("Freight/Expenses")
            columns.append("Net Value")
        else:
            columns = [
                "Month/Period",
                "Item Name",
                "Purchased Qty",
                "Average Rate",
                "Taxable Value",
                "Associated Taxes",
                "Net Purchase Value",
            ]
        return {"rows": display, "columns": columns}

    def gst_purchase_detail(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        opts = parse_gst_filters(params)
        types = purchase_document_types(include_dn_cn=opts["show_dn_cn"], include_expense=True)
        placeholders = ",".join("?" for _ in types)
        extra = ""
        sql_params: list[Any] = [financial_year_id, date_from, date_to, *types]
        if opts["party_id"]:
            extra += " AND d.party_id = ?"
            sql_params.append(opts["party_id"])
        if opts["gstin_query"]:
            extra += " AND COALESCE(p.gstin, '') LIKE ?"
            sql_params.append(f"%{opts['gstin_query']}%")
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_date,
                    d.document_number,
                    COALESCE(p.name, '') AS supplier_name,
                    COALESCE(p.gstin, '') AS supplier_gstin,
                    COALESCE(dl.hsn_code, c.hsn_code, '') AS hsn_code,
                    dl.amount_paise AS taxable_paise,
                    COALESCE(tax.cgst_paise, 0) AS cgst_paise,
                    COALESCE(tax.sgst_paise, 0) AS sgst_paise,
                    COALESCE(tax.igst_paise, 0) AS igst_paise,
                    d.document_type
                FROM document d
                JOIN document_line dl ON dl.document_id = d.document_id
                JOIN commodity c ON c.commodity_id = dl.commodity_id
                LEFT JOIN party p ON p.party_id = d.party_id
                {TAX_AGG_SQL}
                WHERE d.financial_year_id = ?
                  AND d.status = 'posted'
                  AND d.document_date BETWEEN ? AND ?
                  AND d.document_type IN ({placeholders})
                  {extra}
                ORDER BY d.document_date, d.document_number, dl.line_number
                """,
                sql_params,
            ).fetchall()
        display: list[dict[str, str]] = []
        for row in rows:
            eligible = "Y" if int(row["igst_paise"] or row["cgst_paise"] or row["sgst_paise"]) else "N"
            if opts["itc_eligibility"] == "eligible" and eligible != "Y":
                continue
            if opts["itc_eligibility"] == "ineligible" and eligible == "Y":
                continue
            display.append(
                {
                    "Invoice Date": str(row["document_date"]),
                    "Invoice No": str(row["document_number"]),
                    "Supplier Name": str(row["supplier_name"]),
                    "Supplier GSTIN": str(row["supplier_gstin"]),
                    "HSN Code": str(row["hsn_code"]),
                    "Taxable Value": _rupees(int(row["taxable_paise"])),
                    "CGST": _rupees(int(row["cgst_paise"])),
                    "SGST": _rupees(int(row["sgst_paise"])),
                    "IGST": _rupees(int(row["igst_paise"])),
                    "ITC Available (Y/N)": eligible,
                }
            )
        columns = [
            "Invoice Date",
            "Invoice No",
            "Supplier Name",
            "Supplier GSTIN",
            "HSN Code",
            "Taxable Value",
            "CGST",
            "SGST",
            "IGST",
            "ITC Available (Y/N)",
        ]
        return {"rows": display, "columns": columns}

    def gstr1(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        opts = parse_gst_filters(params)
        bills = self.service.bill_wise_gst_detail(
            financial_year_id, date_from, date_to, "sale", filters=params
        )
        with self.databases.connect(self.database_path) as connection:
            tax_rows = connection.execute(
                f"""
                SELECT
                    d.document_id,
                    d.document_number,
                    dc.rate_decimal,
                    dc.code,
                    dc.final_amount_paise,
                    d.subtotal_paise
                FROM document d
                JOIN document_charge dc ON dc.document_id = d.document_id
                WHERE d.financial_year_id = ?
                  AND d.status = 'posted'
                  AND d.document_date BETWEEN ? AND ?
                  AND dc.is_tax = 1
                """,
                (financial_year_id, date_from, date_to),
            ).fetchall()
        tax_by_doc: dict[str, list[dict[str, Any]]] = {}
        for tr in tax_rows:
            tax_by_doc.setdefault(str(tr["document_id"]), []).append(dict(tr))
        display: list[dict[str, str]] = []
        for bill in bills:
            gstin = str(bill.get("gstin") or "")
            inv_val = int(bill.get("grand_total_paise") or 0)
            if opts["invoice_type"] == "b2b" and not gstin:
                continue
            if opts["invoice_type"] == "b2c_large" and (gstin or inv_val <= 250_000_00):
                continue
            if opts["invoice_type"] == "b2c_small" and gstin:
                continue
            doc_id = str(bill.get("document_id") or "")
            charges = tax_by_doc.get(doc_id, [])
            rate = ""
            igst = cgst = sgst = cess = 0
            for ch in charges:
                code = str(ch["code"]).upper()
                amt = int(ch["final_amount_paise"])
                if "IGST" in code:
                    igst += amt
                elif "CGST" in code:
                    cgst += amt
                elif "SGST" in code:
                    sgst += amt
                elif "CESS" in code:
                    cess += amt
                if ch.get("rate_decimal") is not None and not rate:
                    rate = str(ch["rate_decimal"])
            display.append(
                {
                    "GSTIN/UIN of Recipient": gstin or "URP",
                    "Receiver Name": str(bill.get("party_name") or ""),
                    "Invoice No": str(bill.get("document_number") or ""),
                    "Invoice Date": str(bill.get("document_date") or ""),
                    "Invoice Value": _rupees(inv_val),
                    "POS": "",
                    "Reverse Charge (Y/N)": "N",
                    "Invoice Type": "Regular",
                    "Rate (%)": rate,
                    "Taxable Value": _rupees(int(bill.get("taxable_paise") or 0)),
                    "Integrated Tax": _rupees(igst),
                    "Central Tax": _rupees(cgst),
                    "State Tax": _rupees(sgst),
                    "Cess": _rupees(cess),
                }
            )
        payload = self.service.gstr1_payload(
            financial_year_id,
            date_from,
            date_to,
            validate=bool(str(params.get("validate_gstr1") or "").lower() in {"1", "true", "yes"}),
        )
        columns = [
            "GSTIN/UIN of Recipient",
            "Receiver Name",
            "Invoice No",
            "Invoice Date",
            "Invoice Value",
            "POS",
            "Reverse Charge (Y/N)",
            "Invoice Type",
            "Rate (%)",
            "Taxable Value",
            "Integrated Tax",
            "Central Tax",
            "State Tax",
            "Cess",
        ]
        return {"rows": display, "columns": columns, "export": payload, "json": json.dumps(payload, indent=2)}

    def debit_credit_notes(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        opts = parse_gst_filters(params)
        types: tuple[str, ...] = ()
        if opts["note_type"] in {"debit", "both"}:
            types += ("gst_debit_note",)
        if opts["note_type"] in {"credit", "both"}:
            types += ("gst_credit_note",)
        if not types:
            types = ("gst_debit_note", "gst_credit_note")
        placeholders = ",".join("?" for _ in types)
        extra = ""
        sql_params: list[Any] = [financial_year_id, date_from, date_to, *types]
        if opts["party_id"]:
            extra += " AND d.party_id = ?"
            sql_params.append(opts["party_id"])
        with self.databases.connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    d.document_id,
                    d.document_number,
                    d.document_date,
                    d.document_type,
                    d.header_metadata_json,
                    d.subtotal_paise,
                    COALESCE(p.name, '') AS party_name,
                    COALESCE(p.gstin, '') AS gstin,
                    COALESCE(tax.cgst_paise, 0) AS cgst_paise,
                    COALESCE(tax.sgst_paise, 0) AS sgst_paise,
                    COALESCE(tax.igst_paise, 0) AS igst_paise
                FROM document d
                LEFT JOIN party p ON p.party_id = d.party_id
                {TAX_AGG_SQL}
                WHERE d.financial_year_id = ?
                  AND d.status = 'posted'
                  AND d.document_date BETWEEN ? AND ?
                  AND d.document_type IN ({placeholders})
                  {extra}
                ORDER BY d.document_date, d.document_number
                """,
                sql_params,
            ).fetchall()
        display: list[dict[str, str]] = []
        for row in rows:
            meta = json.loads(str(row["header_metadata_json"] or "{}"))
            note_type = "Debit Note" if row["document_type"] == "gst_debit_note" else "Credit Note"
            display.append(
                {
                    "Original Invoice No": str(meta.get("original_invoice_no") or meta.get("bill_no") or ""),
                    "Original Invoice Date": str(meta.get("original_invoice_date") or meta.get("bill_date") or ""),
                    "Note No": str(meta.get("d_note_no") or meta.get("c_note_no") or row["document_number"]),
                    "Note Date": str(row["document_date"]),
                    "Note Type": note_type,
                    "Party Name": str(row["party_name"]),
                    "GSTIN": str(row["gstin"]),
                    "Taxable Value": _rupees(int(row["subtotal_paise"])),
                    "CGST": _rupees(int(row["cgst_paise"])),
                    "SGST": _rupees(int(row["sgst_paise"])),
                    "IGST": _rupees(int(row["igst_paise"])),
                    "Reason for Issuance": str(meta.get("reason") or meta.get("remarks") or ""),
                }
            )
        columns = [
            "Original Invoice No",
            "Original Invoice Date",
            "Note No",
            "Note Date",
            "Note Type",
            "Party Name",
            "GSTIN",
            "Taxable Value",
            "CGST",
            "SGST",
            "IGST",
            "Reason for Issuance",
        ]
        return {"rows": display, "columns": columns}

    def hsn_wise(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """GSTR-1 Table 12 — HSN summary with freight/expense apportionment."""
        opts = parse_gst_filters(params)
        side = opts["transaction_side"]
        doc_types: tuple[str, ...] = ()
        if side in {"sale", "both"}:
            doc_types = doc_types + sale_document_types(include_dn_cn=True)
        if side in {"purchase", "both"}:
            doc_types = doc_types + purchase_document_types(include_dn_cn=True, include_expense=True)
        doc_types = tuple(dict.fromkeys(doc_types))
        with self.databases.connect(self.database_path) as connection:
            documents = load_apportioned_documents_for_period(
                connection,
                financial_year_id,
                date_from,
                date_to,
                doc_types,
            )
        buckets = build_hsn_summary_from_documents(documents)
        display: list[dict[str, str]] = []
        for row in buckets:
            hsn = str(row["hsn_code"])
            if opts["hsn_code"] and opts["hsn_code"] not in hsn:
                continue
            taxable = int(row["taxable_value_paise"])
            if taxable <= 0 and int(row["total_value_paise"]) <= 0:
                continue
            qty = row["quantity"]
            display.append(
                {
                    "HSN/SAC": hsn,
                    "Description": str(row["description"]),
                    "UQC (Unit Quantity Code)": str(row["uqc"]),
                    "Total Quantity": f"{qty:.3f}",
                    "Total Value": _rupees(int(row["total_value_paise"])),
                    "Taxable Value": _rupees(taxable),
                    "Integrated Tax": _rupees(int(row["igst_paise"])),
                    "Central Tax": _rupees(int(row["cgst_paise"])),
                    "State/UT Tax": _rupees(int(row["sgst_paise"])),
                    "Cess": _rupees(int(row["cess_paise"])),
                }
            )
        columns = [
            "HSN/SAC",
            "Description",
            "UQC (Unit Quantity Code)",
            "Total Quantity",
            "Total Value",
            "Taxable Value",
            "Integrated Tax",
            "Central Tax",
            "State/UT Tax",
            "Cess",
        ]
        return {
            "rows": display,
            "columns": columns,
            "title": "GSTR-1 Table 12 — HSN-wise summary of outward/inward supplies",
        }

    def gstr3b(self, financial_year_id: str, date_from: str, date_to: str) -> dict[str, Any]:
        summary = self.service.gst_purchase_sale_summary(financial_year_id, date_from, date_to)
        sale_taxable = int(summary["sale_taxable_paise"])
        sale_tax = int(summary["sale_tax_paise"])
        pur_taxable = int(summary["purchase_taxable_paise"])
        pur_tax = int(summary["purchase_tax_paise"])
        sections = [
            {
                "title": "3.1 Outward supplies and inward supplies liable to reverse charge",
                "rows": [
                    {
                        "Nature of Supplies": "Taxable outward supplies",
                        "Total Taxable Value": _rupees(sale_taxable),
                        "IGST": _rupees(0),
                        "CGST": _rupees(sale_tax // 2 if sale_tax else 0),
                        "SGST": _rupees(sale_tax // 2 if sale_tax else 0),
                        "Cess": _rupees(0),
                    },
                    {
                        "Nature of Supplies": "Inward supplies (reverse charge)",
                        "Total Taxable Value": _rupees(0),
                        "IGST": _rupees(0),
                        "CGST": _rupees(0),
                        "SGST": _rupees(0),
                        "Cess": _rupees(0),
                    },
                ],
            },
            {
                "title": "3.2 Interstate supplies made to unregistered persons",
                "rows": [
                    {
                        "Nature of Supplies": "Inter-state supplies to unregistered",
                        "Total Taxable Value": _rupees(0),
                        "IGST": _rupees(0),
                        "CGST": _rupees(0),
                        "SGST": _rupees(0),
                        "Cess": _rupees(0),
                    }
                ],
            },
            {
                "title": "4.0 Eligible ITC",
                "rows": [
                    {
                        "Nature of Supplies": "ITC on imports / inward supplies",
                        "Total Taxable Value": _rupees(pur_taxable),
                        "IGST": _rupees(0),
                        "CGST": _rupees(pur_tax // 2 if pur_tax else 0),
                        "SGST": _rupees(pur_tax // 2 if pur_tax else 0),
                        "Cess": _rupees(0),
                    }
                ],
            },
            {
                "title": "5.0 Exempt, nil, and non-GST inward supplies",
                "rows": [
                    {
                        "Nature of Supplies": "Exempt / nil rated inward",
                        "Total Taxable Value": _rupees(0),
                        "IGST": _rupees(0),
                        "CGST": _rupees(0),
                        "SGST": _rupees(0),
                        "Cess": _rupees(0),
                    }
                ],
            },
        ]
        flat: list[dict[str, str]] = []
        for section in sections:
            flat.append({"Nature of Supplies": f"— {section['title']} —", "Total Taxable Value": ""})
            flat.extend(section["rows"])
        columns = ["Nature of Supplies", "Total Taxable Value", "IGST", "CGST", "SGST", "Cess"]
        return {
            "rows": flat,
            "columns": columns,
            "sections": sections,
            "net_tax_payable_paise": int(summary["net_tax_paise"]),
        }

    def gstr2b(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        from .gstr2b_service import Gstr2bReconciliationService

        opts = parse_gst_filters(params)
        file_path = str(params.get("gstr2b_file_path") or "").strip()
        tolerance_paise = int(params.get("tax_tolerance_paise") or 100)
        if file_path:
            service = Gstr2bReconciliationService(self.databases, self.database_path)
            result = service.reconcile_from_file(
                financial_year_id,
                date_from,
                date_to,
                file_path,
                tolerance_paise=tolerance_paise,
            )
            display = service.display_rows(result)
            status_filter = opts["reconciliation_status"]
            if status_filter != "all":
                bucket_map = {
                    "matched": "matched",
                    "probable": "probable_match",
                    "mismatched": "probable_match",
                    "in_books_not_in_2b": "in_books_not_in_2b",
                    "in_2b_not_in_books": "in_2b_not_in_books",
                    "missing": "in_2b_not_in_books",
                }
                want_bucket = bucket_map.get(status_filter)
                if want_bucket:
                    display = [row for row in display if row.get("status_bucket") == want_bucket]
                if status_filter == "missing":
                    display = [
                        row
                        for row in display
                        if row.get("status_bucket")
                        in {"in_books_not_in_2b", "in_2b_not_in_books"}
                    ]
            columns = [
                key
                for key in (display[0].keys() if display else [])
                if key != "status_bucket"
            ] if display else [
                "Status",
                "Suggested Action",
                "Match Tier",
                "Supplier GSTIN",
                "Trade Name",
                "2B Invoice No",
                "Books Invoice No",
                "2B Taxable",
                "Books Taxable",
                "2B Tax",
                "Books Tax",
                "Tax Diff (₹)",
                "Document Id",
            ]
            return {
                "rows": display,
                "columns": columns,
                "summary": result.get("summary"),
                "portal_summary": result.get("portal_summary"),
            }

        bills = self.service.bill_wise_gst_detail(
            financial_year_id, date_from, date_to, "purchase", filters={"show_dn_cn": "Y", "show_exp_detail": "Y"}
        )
        display = []
        for bill in bills:
            gstin = str(bill.get("gstin") or "")
            status = "Matched" if gstin else "Missing"
            if opts["reconciliation_status"] == "matched" and status != "Matched":
                continue
            if opts["reconciliation_status"] == "missing" and status != "Missing":
                continue
            if opts["reconciliation_status"] == "mismatched" and status != "Mismatched":
                continue
            taxable = int(bill.get("taxable_paise") or 0)
            total_tax = int(bill.get("total_tax_paise") or 0)
            display.append(
                {
                    "Supplier GSTIN": gstin,
                    "Trade Name": str(bill.get("party_name") or ""),
                    "Invoice No": str(bill.get("document_number") or ""),
                    "Invoice Date": str(bill.get("document_date") or ""),
                    "Invoice Value": _rupees(int(bill.get("grand_total_paise") or 0)),
                    "Taxable Value": _rupees(taxable),
                    "CGST": _rupees(total_tax // 2 if total_tax else 0),
                    "SGST": _rupees(total_tax // 2 if total_tax else 0),
                    "IGST": _rupees(0),
                    "ITC Availability": "Y" if total_tax else "N",
                    "GSTR-1 Filing Date by Supplier": "",
                }
            )
        columns = [
            "Supplier GSTIN",
            "Trade Name",
            "Invoice No",
            "Invoice Date",
            "Invoice Value",
            "Taxable Value",
            "CGST",
            "SGST",
            "IGST",
            "ITC Availability",
            "GSTR-1 Filing Date by Supplier",
        ]
        return {"rows": display, "columns": columns}

    def itc_reversed_claimed(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        opts = parse_gst_filters(params)
        action = opts["itc_action"]
        if action == "claimed":
            rows = self.service.gst_itc_report(financial_year_id, date_from, date_to, kind="availed")
        elif action == "reversed":
            rows = self.service.gst_itc_report(financial_year_id, date_from, date_to, kind="reversed")
        else:
            rows = self.service.gst_itc_report(
                financial_year_id, date_from, date_to, kind="availed"
            ) + self.service.gst_itc_report(financial_year_id, date_from, date_to, kind="reversed")
        display: list[dict[str, str]] = []
        for row in rows:
            rule = str(row.get("label") or row.get("code") or "")
            if opts["reversal_rule"] != "all" and opts["reversal_rule"].replace(" ", "").lower() not in rule.lower():
                if opts["reversal_rule"] not in rule:
                    continue
            tax = int(row.get("tax_paise") or 0)
            display.append(
                {
                    "Document No": str(row.get("document_number") or ""),
                    "Document Date": str(row.get("document_date") or ""),
                    "Supplier Name": str(row.get("party_name") or ""),
                    "Reversal Reason/Rule": rule,
                    "Taxable Value": _rupees(0),
                    "IGST": _rupees(tax if "IGST" in str(row.get("code")).upper() else 0),
                    "CGST": _rupees(tax if "CGST" in str(row.get("code")).upper() else 0),
                    "SGST": _rupees(tax if "SGST" in str(row.get("code")).upper() else 0),
                    "Total ITC Reversed/Claimed": _rupees(abs(tax)),
                }
            )
        columns = [
            "Document No",
            "Document Date",
            "Supplier Name",
            "Reversal Reason/Rule",
            "Taxable Value",
            "IGST",
            "CGST",
            "SGST",
            "Total ITC Reversed/Claimed",
        ]
        return {"rows": display, "columns": columns}

    def itc_availed(
        self,
        financial_year_id: str,
        date_from: str,
        date_to: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        opts = parse_gst_filters(params)
        rows = self.service.gst_itc_report(financial_year_id, date_from, date_to, kind="availed")
        display: list[dict[str, str]] = []
        for row in rows:
            code = str(row.get("code") or "").upper()
            if "CAPITAL" in code:
                category = "Capital Goods"
            elif "SERVICE" in code:
                category = "Input Services"
            else:
                category = "Inputs"
            cat_filter = opts["itc_category"]
            if cat_filter not in {"all", ""}:
                if cat_filter in {"capital goods", "capital"} and category != "Capital Goods":
                    continue
                if cat_filter in {"input services", "services"} and category != "Input Services":
                    continue
                if cat_filter in {"inputs", "input"} and category != "Inputs":
                    continue
            tax = int(row.get("tax_paise") or 0)
            display.append(
                {
                    "Invoice No": str(row.get("document_number") or ""),
                    "Invoice Date": str(row.get("document_date") or ""),
                    "Supplier Name": str(row.get("party_name") or ""),
                    "Category (Capital Goods/Services)": category,
                    "Taxable Value": _rupees(0),
                    "CGST": _rupees(tax if "CGST" in code else 0),
                    "SGST": _rupees(tax if "SGST" in code else 0),
                    "IGST": _rupees(tax if "IGST" in code else 0),
                    "Total ITC": _rupees(tax),
                    "Capital Asset Depreciation Status": "N/A",
                }
            )
        columns = [
            "Invoice No",
            "Invoice Date",
            "Supplier Name",
            "Category (Capital Goods/Services)",
            "Taxable Value",
            "CGST",
            "SGST",
            "IGST",
            "Total ITC",
            "Capital Asset Depreciation Status",
        ]
        return {"rows": display, "columns": columns}

    def gstr9(self, financial_year_id: str, date_from: str, date_to: str) -> dict[str, Any]:
        summary = self.service.gst_purchase_sale_summary(financial_year_id, date_from, date_to)
        sections = [
            {
                "title": "Table 4: Details of advances, inward and outward supplies",
                "rows": [
                    {
                        "Description": "Outward taxable supplies",
                        "Taxable Value": _rupees(int(summary["sale_taxable_paise"])),
                        "Central Tax": _rupees(int(summary["sale_tax_paise"]) // 2),
                        "State Tax": _rupees(int(summary["sale_tax_paise"]) // 2),
                        "Integrated Tax": _rupees(0),
                        "Cess": _rupees(0),
                    },
                    {
                        "Description": "Inward taxable supplies",
                        "Taxable Value": _rupees(int(summary["purchase_taxable_paise"])),
                        "Central Tax": _rupees(int(summary["purchase_tax_paise"]) // 2),
                        "State Tax": _rupees(int(summary["purchase_tax_paise"]) // 2),
                        "Integrated Tax": _rupees(0),
                        "Cess": _rupees(0),
                    },
                ],
            },
            {
                "title": "Table 5: Outward supplies where tax is not payable",
                "rows": [
                    {
                        "Description": "Exempt / nil rated outward",
                        "Taxable Value": _rupees(0),
                        "Central Tax": _rupees(0),
                        "State Tax": _rupees(0),
                        "Integrated Tax": _rupees(0),
                        "Cess": _rupees(0),
                    }
                ],
            },
            {
                "title": "Table 6: Details of ITC availed",
                "rows": [
                    {
                        "Description": "ITC availed on purchases",
                        "Taxable Value": _rupees(int(summary["purchase_taxable_paise"])),
                        "Central Tax": _rupees(int(summary["purchase_tax_paise"]) // 2),
                        "State Tax": _rupees(int(summary["purchase_tax_paise"]) // 2),
                        "Integrated Tax": _rupees(0),
                        "Cess": _rupees(0),
                    }
                ],
            },
            {
                "title": "Table 7: Details of ITC reversed",
                "rows": [
                    {
                        "Description": "ITC reversed",
                        "Taxable Value": _rupees(0),
                        "Central Tax": _rupees(0),
                        "State Tax": _rupees(0),
                        "Integrated Tax": _rupees(0),
                        "Cess": _rupees(0),
                    }
                ],
            },
        ]
        flat: list[dict[str, str]] = []
        for section in sections:
            flat.append({"Description": f"— {section['title']} —", "Taxable Value": ""})
            flat.extend(section["rows"])
        columns = ["Description", "Taxable Value", "Central Tax", "State Tax", "Integrated Tax", "Cess"]
        return {"rows": flat, "columns": columns, "sections": sections}

    def clause_44(self, financial_year_id: str, date_from: str, date_to: str) -> dict[str, Any]:
        raw = self.service.clause_44_export(financial_year_id, date_from, date_to)
        export = raw.get("export") or {}
        reg = export.get("registered_suppliers") or []
        unreg = export.get("unregistered_suppliers") or []
        total_exp = sum(int(r.get("amount_paise") or 0) for r in reg + unreg)
        reg_total = sum(int(r.get("amount_paise") or 0) for r in reg)
        unreg_total = sum(int(r.get("amount_paise") or 0) for r in unreg)
        row = {
            "Total Expenditure Incurred during the year": _rupees(total_exp),
            "Expenditure on entities exempt from GST": _rupees(0),
            "Expenditure on composition scheme entities": _rupees(0),
            "Expenditure on other registered entities": _rupees(reg_total),
            "Total payment to registered entities": _rupees(reg_total),
            "Expenditure on entities not registered under GST": _rupees(unreg_total),
        }
        columns = list(row.keys())
        return {
            "rows": [row],
            "columns": columns,
            "export": export,
            "json": raw.get("json") or json.dumps(export, indent=2),
        }
