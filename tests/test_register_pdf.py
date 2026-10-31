"""Register PDF generation."""

from pathlib import Path

from anaj_erp.register_pdf import RegisterPdfPrinter


def test_cash_book_pdf_writes_file(tmp_path: Path) -> None:
    destination = tmp_path / "cash.pdf"
    RegisterPdfPrinter.cash_book(
        "Test Co",
        {
            "entries": [
                {
                    "entry_date": "2026-04-01",
                    "narration": "Opening",
                    "debit_paise": 10000,
                    "credit_paise": 0,
                    "running_balance_paise": 10000,
                }
            ],
            "closing_balance_paise": 10000,
        },
        date_from="2026-04-01",
        date_to="2026-04-30",
        destination=destination,
    )
    assert destination.is_file()
    assert destination.stat().st_size > 500
