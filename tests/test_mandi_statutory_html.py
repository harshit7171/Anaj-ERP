"""Statutory Form-J / Form-I HTML renderer tests."""

from __future__ import annotations

from anaj_erp.mandi_statutory_html import MandiStatutoryHtmlRenderer, STATUTORY_COPIES


def test_form_j_html_contains_farmer_and_three_copies() -> None:
    header = {
        "document_type": "form_j",
        "document_number": "J-1001",
        "document_date": "2026-04-01",
        "party_name": "Ram Kumar",
        "from_place": "Karnal",
        "subtotal_paise": 500000,
        "grand_total_paise": 450000,
    }
    lines = [
        {
            "commodity_name": "Wheat",
            "bags_scaled": 10,
            "quantity_scaled": 500000,
            "rate_paise": 220000,
            "amount_paise": 500000,
            "metadata": {"gate_pass_number": "GP-9"},
        }
    ]
    charges = [
        {"code": "MARKET_FEE", "label": "Market fee", "final_amount_paise": 50000},
    ]
    html = MandiStatutoryHtmlRenderer().render(header, lines, charges, columns=80, copy_count=3)
    assert "Ram Kumar" in html
    assert "J-1001" in html
    assert "Wheat" in html
    for _key, label_en, _label_hi in STATUTORY_COPIES:
        assert label_en in html
    assert html.count("mandi-copy-sheet") >= 3
    assert "@media print" in html or "mandi-statutory-print" in html
