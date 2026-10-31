"""Phase 3 master tables and Phase 4 document types."""

from pathlib import Path

import pytest

from anaj_erp.database import DatabaseManager
from anaj_erp.documents import DocumentService
from anaj_erp.errors import ValidationError
from anaj_erp.masters import MasterService


def test_city_master_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data")
    databases.initialize()
    company = databases.create_company("Master Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    saved = masters.save_city(
        {
            "city_code": "1",
            "name": "Karnal",
            "state_name": "Haryana",
            "state_code": "06",
            "district_name": "Karnal",
            "country": "India",
            "focal_point": "N",
            "pincode": "132001",
        }
    )
    assert saved["name"] == "Karnal"
    cities = masters.list_cities()
    assert any(str(row["city_id"]) == str(saved["city_id"]) for row in cities)
    loaded = masters.get_city("1")
    assert loaded["name"] == "Karnal"
    masters.delete_city(str(saved["city_id"]))
    with pytest.raises(ValidationError):
        masters.get_city(str(saved["city_id"]))


def test_transport_master_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_transport")
    databases.initialize()
    company = databases.create_company("Transport Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    saved = masters.save_transport(
        {
            "transport_code": "1",
            "name": "Blue Line Carriers",
            "gstin": "06AABCU9603R1ZM",
            "vehicle_details": "HR-01-AB-1234",
            "phone": "9999999999",
        }
    )
    assert saved["name"] == "Blue Line Carriers"
    loaded = masters.get_transport("1")
    assert loaded["gstin"] == "06AABCU9603R1ZM"
    assert loaded["vehicle_details"] == "HR-01-AB-1234"
    masters.delete_transport(str(saved["transport_id"]))
    with pytest.raises(ValidationError):
        masters.get_transport(str(saved["transport_id"]))


def test_i_form_expense_define_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_iform_exp")
    databases.initialize()
    company = databases.create_company("IForm Exp Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    item = masters.save_item({"name": "BARDANA"})
    commodity_id = str(item["commodity_id"])
    saved = masters.save_i_form_expense_define(
        {
            "commodity_id": commodity_id,
            "effective_date": "2026-10-20",
            "dami_on": "A",
            "lines": [{"expense_name": "I Form Labour", "rate": 7.5, "rate_on": "A"}],
        }
    )
    loaded = masters.get_i_form_expense_define(commodity_id, "2026-10-20")
    assert loaded["define_id"]
    labour = next(
        row for row in loaded["lines"] if row["expense_name"] == "I Form Labour"
    )
    assert float(labour["rate"]) == 7.5
    masters.delete_i_form_expense_define(str(saved["define_id"]))
    blank = masters.get_i_form_expense_define(commodity_id, "2026-10-20")
    assert blank["define_id"] == ""


def test_expense_master_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_expense")
    databases.initialize()
    company = databases.create_company("Expense Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    saved = masters.save_expense_master(
        {
            "name": "PADDY BASMATI EXP",
            "mandi_name": "Karnal",
            "lines": [
                {
                    "expense_name": "MKT FEES",
                    "nature": "Market",
                    "expenses_on": "Amt",
                    "rate": 1.0,
                    "stage": 1,
                    "account_name": "Market Fee A/c",
                    "dr_cr": "C",
                    "r_off": "N",
                }
            ],
        }
    )
    loaded = masters.get_expense_master("PADDY BASMATI EXP")
    assert loaded["name"] == "PADDY BASMATI EXP"
    assert len(loaded["lines"]) == 1
    masters.delete_expense_master(str(saved["expense_master_id"]))
    with pytest.raises(ValidationError):
        masters.get_expense_master("PADDY BASMATI EXP")


def test_stock_entry_master_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_stock_entry")
    databases.initialize()
    company = databases.create_company("Stock Entry Test Co", 2026)
    company_id = str(company["company_id"])
    year = databases.list_financial_years(company_id)[0]
    fy_id = str(year["financial_year_id"])
    masters = MasterService(databases, company_id)
    item = masters.save_item({"name": "WHEAT"})
    commodity_id = str(item["commodity_id"])
    saved = masters.save_stock_entry_master(
        fy_id,
        {
            "entry_kind": "opening",
            "entry_date": "2026-04-01",
            "show_opening": True,
            "lines": [
                {
                    "commodity_id": commodity_id,
                    "item_name": "WHEAT",
                    "unit": "Bags",
                    "qty": "10",
                    "weight": "500",
                    "amount": "25000",
                    "mm": "1",
                }
            ],
        },
    )
    assert saved["entry_kind"] == "opening"
    loaded = masters.get_stock_entry(fy_id, "", entry_kind="opening", entry_date="2026-04-01")
    assert len(loaded["lines"]) == 1
    with databases.connect(masters.database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS c FROM opening_stock WHERE financial_year_id = ?",
            (fy_id,),
        ).fetchone()["c"]
    assert int(count) == 1
    closing = masters.save_stock_entry_master(
        fy_id,
        {
            "entry_kind": "closing",
            "entry_date": "2026-10-20",
            "lines": [
                {
                    "commodity_id": commodity_id,
                    "item_name": "WHEAT",
                    "qty": "5",
                    "weight": "250",
                    "rate": "50",
                    "amount": "12500",
                }
            ],
        },
    )
    assert closing["entry_kind"] == "closing"
    masters.delete_stock_entry_master(fy_id, str(saved["stock_entry_id"]))
    with pytest.raises(ValidationError):
        masters.get_stock_entry(fy_id, str(saved["stock_entry_id"]))


def test_ifsc_master_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_ifsc")
    databases.initialize()
    company = databases.create_company("IFSC Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    saved = masters.save_ifsc(
        {
            "ifsc_number": "3",
            "ifsc_code": "HDFC0001234",
            "bank_name": "HDFC BANK",
            "city": "KARNAL",
            "address": "Sector 12",
        }
    )
    assert str(saved["ifsc_code"]) == "HDFC0001234"
    assert str(saved["ifsc_number"]) == "3"
    loaded = masters.get_ifsc("HDFC0001234")
    assert loaded["city"] == "KARNAL"
    records = masters.list_ifsc()
    assert len(records) == 1
    masters.delete_ifsc(str(saved["ifsc_id"]))
    with pytest.raises(ValidationError):
        masters.get_ifsc("HDFC0001234")


def test_bank_master_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_bank")
    databases.initialize()
    company = databases.create_company("Bank Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    saved = masters.save_bank({"bank_code": "7", "name": "HDFC BANK LTD"})
    assert saved["name"] == "HDFC BANK LTD"
    assert str(saved["bank_code"]) == "7"
    loaded = masters.get_bank("7")
    assert loaded["bank_id"] == saved["bank_id"]
    banks = masters.list_banks()
    assert len(banks) == 1
    masters.delete_bank(str(saved["bank_id"]))
    with pytest.raises(ValidationError):
        masters.get_bank("7")


def test_cheque_print_setting_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_cheque")
    databases.initialize()
    company = databases.create_company("Cheque Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    saved = masters.save_cheque_print_setting(
        {
            "bank_name": "HDFC BANK LTD -175",
            "width_of_chq": "20",
            "height_of_chq": "9",
            "printer_mode": "P",
            "date_font": "10",
            "show_star": "N",
        }
    )
    assert saved["bank_name"] == "HDFC BANK LTD -175"
    assert str(saved["width_of_chq"]) == "20"
    loaded = masters.get_cheque_print_setting("HDFC BANK LTD -175")
    assert str(loaded["height_of_chq"]) == "9"
    settings = masters.list_cheque_print_settings()
    assert len(settings) == 1
    setting_id = str(saved["cheque_setting_id"])
    masters.delete_cheque_print_setting(setting_id)
    with pytest.raises(ValidationError):
        masters.get_cheque_print_setting(setting_id)


def test_item_entry_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_item")
    databases.initialize()
    company = databases.create_company("Item Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    saved = masters.save_item(
        {
            "name": "PADDY BASMATI",
            "item_code": "42",
            "item_group": "PADDY",
            "sub_group": "BASMATI",
            "rate_per": "Bags",
            "bardana_item": "No",
            "paddy": "Yes",
            "hsn_code": "1006",
            "stockable": "Yes",
        }
    )
    assert saved["name"] == "PADDY BASMATI"
    assert str(saved["item_code"]) == "42"
    assert str(saved["item_group"]) == "PADDY"
    loaded = masters.get_item("42")
    assert loaded["name"] == "PADDY BASMATI"
    assert str(loaded["paddy"]) == "Yes"
    items = masters.list_items()
    assert any(str(row["name"]) == "PADDY BASMATI" for row in items)
    commodity_id = str(saved["commodity_id"])
    masters.delete_item(commodity_id)
    with pytest.raises(ValidationError):
        masters.get_item(commodity_id)


def test_trading_account_round_trip(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data_trading")
    databases.initialize()
    company = databases.create_company("Trading Test Co", 2026)
    company_id = str(company["company_id"])
    masters = MasterService(databases, company_id)
    item = masters.save_item({"name": "WHEAT"})
    commodity_id = str(item["commodity_id"])
    saved = masters.save_trading_account(
        {
            "trading_code": "3",
            "name": "Paddy Trading",
            "profit_loss_account": "Trading P&L",
            "raw_commodity_ids": [commodity_id],
            "finished_commodity_ids": [],
        }
    )
    loaded = masters.get_trading_account("3")
    assert loaded["name"] == "Paddy Trading"
    assert commodity_id in [str(x) for x in loaded["raw_commodity_ids"]]
    masters.delete_trading_account(str(saved["trading_account_id"]))
    with pytest.raises(ValidationError):
        masters.get_trading_account("3")


def test_kachi_purchase_document_number(tmp_path: Path) -> None:
    databases = DatabaseManager(tmp_path / "data2")
    databases.initialize()
    company = databases.create_company("Kachi Test Co", 2026)
    company_id = str(company["company_id"])
    years = databases.list_financial_years(company_id)
    year_id = str(years[0]["financial_year_id"])
    documents = DocumentService(databases, company_id)
    number = documents.next_document_number(year_id, "kachi_purchase")
    assert number.startswith("KP-")
