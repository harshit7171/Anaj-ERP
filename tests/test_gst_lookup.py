import pytest

from anaj_erp.gst_lookup import validate_gstin
from anaj_erp.errors import ValidationError


def test_validate_gstin_normalizes() -> None:
    # Known valid sample GSTIN (format + checksum)
    assert validate_gstin("27AAPFU0939F1ZV") == "27AAPFU0939F1ZV"


def test_validate_gstin_rejects_short() -> None:
    with pytest.raises(ValidationError):
        validate_gstin("27AAPFU0939F1Z")
