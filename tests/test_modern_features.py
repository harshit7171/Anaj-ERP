"""Modern competitive feature helpers."""

from anaj_erp.modern_features import whatsapp_url


def test_whatsapp_url_indian_mobile() -> None:
    url = whatsapp_url("9876543210", "Hello farmer")
    assert "wa.me/919876543210" in url
    assert "Hello" in url
