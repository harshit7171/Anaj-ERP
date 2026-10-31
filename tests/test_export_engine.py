"""Tests for multi-format table export."""

from pathlib import Path

import pytest

from anaj_erp.export_engine import TableExportEngine


@pytest.fixture
def sample_rows() -> list[dict[str, str]]:
    return [
        {"party_name": "Ram Singh", "bill_no": "J-101", "amount": "1000.00"},
        {"party_name": "Gopal", "bill_no": "J-102", "amount": "2500.50"},
    ]


def test_csv_and_html_export(tmp_path: Path, sample_rows: list[dict[str, str]]) -> None:
    engine = TableExportEngine(
        title="Mandi Register",
        columns=["party_name", "bill_no", "amount"],
        rows=sample_rows,
    )
    csv_path = engine.export(tmp_path / "reg", "csv")
    html_path = engine.export(tmp_path / "reg", "html")
    assert csv_path.exists()
    assert html_path.exists()
    assert "party_name" in csv_path.read_text(encoding="utf-8-sig")


def test_visible_columns(tmp_path: Path, sample_rows: list[dict[str, str]]) -> None:
    engine = TableExportEngine(
        title="Filtered",
        columns=["party_name", "bill_no", "amount"],
        rows=sample_rows,
        visible_columns=["bill_no", "amount"],
    )
    xml_path = engine.export(tmp_path / "f", "xml")
    text = xml_path.read_text(encoding="utf-8")
    assert "party_name" not in text
    assert "bill_no" in text
