"""Integration tests for masters, documents, ledger, stock and printing."""

from pathlib import Path

from anaj_erp.accounting import AccountingService
from anaj_erp.backup import BackupService
from anaj_erp.database import DatabaseManager
from anaj_erp.documents import DocumentService
from anaj_erp.maintenance import MaintenanceService
from anaj_erp.printing import InvoicePrinter
from anaj_erp.reports import ReportService


def setup_company(tmp_path: Path) -> tuple[DatabaseManager, str, str]:
    """Create one isolated company and return manager, company and year IDs."""
    databases = DatabaseManager(tmp_path / "primary")
    databases.initialize()
    company = databases.create_company("Test Mandi Firm", 2026)
    company_id = company["company_id"]
    year = databases.list_financial_years(company_id)[0]
    return databases, company_id, str(year["financial_year_id"])


def test_sale_invoice_posts_balanced_ledger_stock_and_pdf(tmp_path: Path) -> None:
    """A configured sale posts one transaction across all accounting bands."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    sales = accounting.create_account("Sales", "income")
    party_account = accounting.create_account("AGF Grains", "party")
    commission = accounting.create_account("Commission", "income")
    party = accounting.create_party(
        "AGF Grains Private Ltd.",
        "customer",
        account_id=party_account["account_id"],
    )
    commodity = accounting.create_commodity("Paddy", hsn_code="100610")
    accounting.create_charge_rule(
        code="COMMISSION",
        label="Com. 1.00%",
        transaction_type="sale_invoice",
        basis="amount",
        mode="percentage",
        rate_decimal="1.00",
        direction="add",
        effective_from="2026-04-01",
        ledger_account_id=commission["account_id"],
    )

    documents = DocumentService(databases, company_id)
    posted = documents.post(
        financial_year_id=year_id,
        document_type="sale_invoice",
        document_number="26-27/0001",
        document_date="2026-11-09",
        party_id=party["party_id"],
        main_account_id=sales["account_id"],
        party_account_id=party_account["account_id"],
        lines=[
            {
                "commodity_id": commodity["commodity_id"],
                "description": "PADDY",
                "hsn_code": "100610",
                "bags_scaled": 20,
                "bag_scale": 0,
                "quantity_scaled": 10_000,
                "quantity_scale": 3,
                "rate_paise": 10_000,
                "rate_unit": "quintal",
            }
        ],
        excluded_charge_codes=[
            "DAMI",
            "LABOUR",
            "AUCTION",
            "MARKET_FEE",
            "HRDF",
            "ASSOCIATION",
            "SGST",
            "CGST",
        ],
        header={"vehicle_number": "HR65A-1254", "to_place": "Taraori"},
    )

    assert posted["subtotal_paise"] == 100_000
    assert posted["total_charges_paise"] == 1_000
    assert posted["grand_total_paise"] == 101_000
    trial = accounting.trial_balance(year_id)
    assert sum(int(row["balance_paise"]) for row in trial) == 0
    stock = documents.stock_balance(year_id)
    assert stock[0]["quantity_scaled"] == -10_000

    pdf_path = InvoicePrinter(documents).create_pdf(
        str(posted["document_id"]),
        tmp_path / "invoice.pdf",
    )
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_journal_and_reports_use_posted_vouchers(tmp_path: Path) -> None:
    """Manual journals appear in trial balance, day book and ledger."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    cash = accounting.create_account("Cash", "cash")
    capital = accounting.create_account("Capital", "capital")
    accounting.post_voucher(
        financial_year_id=year_id,
        voucher_type="journal",
        voucher_number="J-1",
        voucher_date="2026-04-01",
        narration="Opening capital",
        lines=[
            {"account_id": cash["account_id"], "debit_paise": 50_000},
            {"account_id": capital["account_id"], "credit_paise": 50_000},
        ],
    )
    reports = ReportService(databases, company_id)
    day_book = reports.day_book(year_id, "2026-04-01", "2026-04-30")
    ledger = reports.account_ledger(
        year_id,
        cash["account_id"],
        "2026-04-01",
        "2026-04-30",
    )

    assert day_book[0]["debit_paise"] == 50_000
    assert day_book[0]["credit_paise"] == 50_000
    assert ledger["closing_balance_paise"] == 50_000


def test_dense_document_metadata_and_milling_directions(tmp_path: Path) -> None:
    """Page-specific metadata persists and one milling job moves stock both ways."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    raw = accounting.create_commodity("Raw Paddy")
    finished = accounting.create_commodity("Basmati Rice")
    documents = DocumentService(databases, company_id)

    posted = documents.post(
        financial_year_id=year_id,
        document_type="milling_inward",
        document_number="MIL-1",
        document_date="2026-10-04",
        party_id=None,
        lines=[
            {
                "commodity_id": raw["commodity_id"],
                "description": "Raw Paddy",
                "bags_scaled": 20,
                "bag_scale": 0,
                "quantity_scaled": 10_000,
                "quantity_scale": 3,
                "rate_paise": 0,
                "metadata": {
                    "section": "inbound",
                    "inventory_direction": "out",
                    "values": {"lotNumber": "LOT-7"},
                },
            },
            {
                "commodity_id": finished["commodity_id"],
                "description": "Basmati Rice",
                "bags_scaled": 14,
                "bag_scale": 0,
                "quantity_scaled": 7_000,
                "quantity_scale": 3,
                "rate_paise": 0,
                "metadata": {
                    "section": "outbound",
                    "inventory_direction": "in",
                    "values": {"byproductCode": "RICE"},
                },
            },
        ],
        header={
            "metadata": {
                "fields": {
                    "processingUnit": "Sheller-1",
                    "batchReference": "BATCH-9",
                    "supervisor": "Operator A",
                }
            }
        },
    )

    saved = documents.get_document(str(posted["document_id"]))
    stock = {
        str(row["commodity_id"]): int(row["quantity_scaled"])
        for row in documents.stock_balance(year_id)
    }

    assert saved["header"]["metadata"]["fields"]["batchReference"] == "BATCH-9"
    assert saved["lines"][0]["metadata"]["values"]["lotNumber"] == "LOT-7"
    assert stock[str(raw["commodity_id"])] == -10_000
    assert stock[str(finished["commodity_id"])] == 7_000

    documents.post(
        financial_year_id=year_id,
        document_type="transfer_challan",
        document_number="TC-1",
        document_date="2026-10-04",
        party_id=None,
        lines=[{
            "commodity_id": finished["commodity_id"],
            "description": "Basmati Rice",
            "bags_scaled": 4,
            "bag_scale": 0,
            "quantity_scaled": 2_000,
            "quantity_scale": 3,
            "rate_paise": 0,
        }],
        header={
            "metadata": {
                "fields": {"fromGodown": "MAIN", "toGodown": "GODOWN-B"}
            }
        },
    )
    transfer_stock = {
        str(row["warehouse_code"]): int(row["quantity_scaled"])
        for row in documents.stock_balance(year_id)
        if str(row["commodity_id"]) == str(finished["commodity_id"])
    }
    assert transfer_stock == {"GODOWN-B": 2_000, "MAIN": 5_000}


def test_form_j_persists_dheri_expenses_bonus_and_numbering(tmp_path: Path) -> None:
    """Form-J keeps mandi details and advances its year-specific number."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    purchase = accounting.create_account("Purchase", "expense")
    farmer_account = accounting.create_account("Farmer Payable", "party")
    farmer = accounting.create_party(
        "Ramesh Kumar",
        "supplier",
        related_name="S/O Mohan Lal",
        account_id=farmer_account["account_id"],
    )
    purchaser = accounting.create_party("Rice Mill", "customer")
    commodity = accounting.create_commodity("Paddy")
    accounting.create_charge_rule(
        code="HAMALI",
        label="Hamali 1%",
        transaction_type="form_j",
        basis="amount",
        mode="percentage",
        rate_decimal="1.00",
        direction="deduct",
        effective_from="2026-04-01",
    )
    accounting.create_charge_rule(
        code="MANDI",
        label="Mandi fee 2%",
        transaction_type="form_j",
        basis="amount",
        mode="percentage",
        rate_decimal="2.00",
        direction="deduct",
        effective_from="2026-04-01",
    )

    documents = DocumentService(databases, company_id)
    assert documents.next_document_number(year_id, "form_j") == "J-1"
    posted = documents.post(
        financial_year_id=year_id,
        document_type="form_j",
        document_number="J-1",
        document_date="2026-10-01",
        party_id=farmer["party_id"],
        main_account_id=purchase["account_id"],
        party_account_id=farmer_account["account_id"],
        excluded_charge_codes=["MANDI"],
        bonus_paise=50_000,
        lines=[
            {
                "commodity_id": commodity["commodity_id"],
                "purchaser_party_id": purchaser["party_id"],
                "gate_pass_number": "GP-88",
                "description": "PADDY",
                "bags_scaled": 20,
                "bag_scale": 0,
                "packing_weight_scaled": 50_000,
                "loose_quantity_scaled": 0,
                "quantity_scaled": 10_000,
                "quantity_scale": 3,
                "rate_paise": 100_000,
                "rate_unit": "quintal",
            }
        ],
        header={
            "due_date": "2026-10-08",
            "gate_pass_required": True,
            "self_purchase": False,
        },
    )

    assert posted["subtotal_paise"] == 1_000_000
    assert posted["total_charges_paise"] == -10_000
    assert posted["bonus_paise"] == 50_000
    assert posted["grand_total_paise"] == 1_040_000
    saved = documents.get_document(str(posted["document_id"]))
    assert saved["header"]["gate_pass_required"] == 1
    assert saved["lines"][0]["purchaser_party_id"] == purchaser["party_id"]
    assert saved["lines"][0]["gate_pass_number"] == "GP-88"
    assert {charge["code"] for charge in saved["charges"]} == {"HAMALI", "BONUS"}
    assert documents.next_document_number(year_id, "form_j") == "J-2"


def test_sale_bill_posts_freight_tax_and_advance_receipt(tmp_path: Path) -> None:
    """Sale invoice stages tax after expenses and atomically receives advance cash."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    sales = accounting.create_account("Sales", "income")
    buyer_account = accounting.create_account("Buyer", "party")
    cash = accounting.create_account("Cash", "cash")
    buyer = accounting.create_party(
        "XYZ Exporter",
        "customer",
        account_id=buyer_account["account_id"],
        gstin="06ABCDE1234F1Z5",
    )
    source = accounting.create_party("ABC Trading Co.", "supplier")
    commodity = accounting.create_commodity("1121 Paddy")

    documents = DocumentService(databases, company_id)
    posted = documents.post(
        financial_year_id=year_id,
        document_type="sale_invoice",
        document_number="S-1",
        document_date="2026-10-02",
        party_id=buyer["party_id"],
        main_account_id=sales["account_id"],
        party_account_id=buyer_account["account_id"],
        lines=[
            {
                "commodity_id": commodity["commodity_id"],
                "source_party_id": source["party_id"],
                "source_reference_number": "123",
                "description": "1121 PADDY",
                "bags_scaled": 56,
                "bag_scale": 0,
                "packing_weight_scaled": 50_000,
                "loose_quantity_scaled": 0,
                "quantity_scaled": 28_000,
                "quantity_scale": 3,
                "rate_paise": 131_000,
                "rate_unit": "quintal",
            },
            {
                "commodity_id": commodity["commodity_id"],
                "source_party_id": source["party_id"],
                "source_reference_number": "124",
                "description": "1121 PADDY",
                "bags_scaled": 59,
                "bag_scale": 0,
                "packing_weight_scaled": 50_000,
                "loose_quantity_scaled": 0,
                "quantity_scaled": 29_500,
                "quantity_scale": 3,
                "rate_paise": 152_100,
                "rate_unit": "quintal",
            },
        ],
        header={
            "freight_paise": 10_000,
            "freight_direction": "add",
            "advance_cash_paise": 500_000,
            "cash_account_id": cash["account_id"],
            "gr_number": "000",
            "gr_date": "2026-10-02",
            "dispatch_time": "13:54",
            "insurance_number": "INS-9",
            "packing_material_transfer": True,
            "stock_sale": True,
            "multi_tax": True,
        },
    )

    assert posted["subtotal_paise"] == 8_154_950
    assert posted["total_charges_paise"] == 570_908
    assert posted["taxable_total_paise"] == 8_735_858
    assert posted["total_tax_paise"] == 436_792
    assert posted["grand_total_paise"] == 9_172_650
    assert posted["advance_receipt_voucher_id"]
    saved = documents.get_document(str(posted["document_id"]))
    assert saved["header"]["balance_paise"] == 8_672_650
    assert saved["header"]["packing_material_transfer"] == 1
    assert saved["lines"][0]["source_party_id"] == source["party_id"]
    assert saved["lines"][0]["source_reference_number"] == "123"
    trial = accounting.trial_balance(year_id)
    assert sum(int(row["balance_paise"]) for row in trial) == 0


def test_form_i_credit_uses_inbound_expenses_and_deducts_bonus(tmp_path: Path) -> None:
    """Form-I Credit adds mandi costs, deducts bonus and receives inventory."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    purchase = accounting.create_account("Purchase", "expense")
    party_account = accounting.create_account("Commission Agent", "party")
    party = accounting.create_party(
        "ABC Trading Co.",
        "supplier",
        account_id=party_account["account_id"],
    )
    commodity = accounting.create_commodity("1121 Paddy")
    documents = DocumentService(databases, company_id)

    posted = documents.post(
        financial_year_id=year_id,
        document_type="form_i_credit",
        document_number="IP-1",
        document_date="2026-10-03",
        party_id=party["party_id"],
        main_account_id=purchase["account_id"],
        party_account_id=party_account["account_id"],
        bonus_paise=10_000,
        lines=[
            {
                "commodity_id": commodity["commodity_id"],
                "description": "1121 PADDY",
                "bags_scaled": 56,
                "bag_scale": 0,
                "packing_weight_scaled": 50_000,
                "loose_quantity_scaled": 0,
                "quantity_scaled": 28_000,
                "quantity_scale": 3,
                "rate_paise": 131_000,
                "rate_unit": "quintal",
            }
        ],
        header={
            "reference_number": "123",
            "bonus_direction": "deduct",
        },
    )

    assert posted["subtotal_paise"] == 3_668_000
    assert posted["total_charges_paise"] == 111_222
    assert posted["taxable_total_paise"] == 3_779_222
    assert posted["signed_bonus_paise"] == -10_000
    assert posted["grand_total_paise"] == 3_769_222
    stock = documents.stock_balance(year_id)
    assert stock[0]["quantity_scaled"] == 28_000
    trial = accounting.trial_balance(year_id)
    assert sum(int(row["balance_paise"]) for row in trial) == 0


def test_backup_restores_only_as_new_company(tmp_path: Path) -> None:
    """Online backup can bootstrap a second installation without overwrite."""
    primary, company_id, _ = setup_company(tmp_path)
    backup_path = BackupService(primary).create_company_backup(
        company_id,
        tmp_path / "company",
    )
    secondary = DatabaseManager(tmp_path / "secondary")
    secondary.initialize()

    restored = BackupService(secondary).restore_new_company(backup_path)

    assert restored["company_id"] == company_id
    assert secondary.list_companies()[0]["name"] == "Test Mandi Firm"


def test_voucher_reversal_preserves_history_and_nets_ledger(tmp_path: Path) -> None:
    """A correction posts opposite lines instead of deleting the original."""
    databases, company_id, year_id = setup_company(tmp_path)
    accounting = AccountingService(databases, company_id)
    cash = accounting.create_account("Cash", "cash")
    expense = accounting.create_account("Labour Expense", "expense")
    posted = accounting.post_voucher(
        financial_year_id=year_id,
        voucher_type="payment",
        voucher_number="P-1",
        voucher_date="2026-05-01",
        narration="Labour paid",
        lines=[
            {"account_id": expense["account_id"], "debit_paise": 10_000},
            {"account_id": cash["account_id"], "credit_paise": 10_000},
        ],
    )

    accounting.reverse_voucher(
        str(posted["voucher_id"]),
        "P-1-R",
        "2026-05-02",
        "Entered against wrong party",
    )

    trial = accounting.trial_balance(year_id)
    assert all(int(row["balance_paise"]) == 0 for row in trial)


def test_pilot_csv_dry_run_and_reconciliation(tmp_path: Path) -> None:
    """Pilot tools validate imports and confirm balanced empty books."""
    databases, company_id, year_id = setup_company(tmp_path)
    csv_path = tmp_path / "accounts.csv"
    csv_path.write_text(
        "name,account_type\nCash,cash\nSales,income\n",
        encoding="utf-8",
    )
    maintenance = MaintenanceService(databases, company_id)

    dry_run = maintenance.import_master_csv("account", csv_path, dry_run=True)
    imported = maintenance.import_master_csv("account", csv_path, dry_run=False)
    reconciliation = maintenance.reconcile(year_id)

    assert dry_run["valid_rows"] == 2
    assert dry_run["imported"] == 0
    assert imported["imported"] == 2
    assert reconciliation["passed"] is True
