"""GSTIN format validation and optional online lookup (requires internet + API key)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .errors import ValidationError

_GSTIN_RE = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)

_GSTIN_CHECK_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def validate_gstin(gstin: str) -> str:
    """Return normalized GSTIN or raise ValidationError."""
    clean = str(gstin or "").strip().upper()
    if len(clean) != 15:
        raise ValidationError("GSTIN must be 15 characters")
    if not _GSTIN_RE.match(clean):
        raise ValidationError("GSTIN format is invalid")
    checksum = clean[-1]
    body = clean[:-1]
    factor = 1
    total = 0
    for char in body:
        code_point = _GSTIN_CHECK_CHARS.index(char)
        product = code_point * factor
        quotient, remainder = divmod(product, 36)
        total += quotient + remainder
        factor = 2 if factor == 1 else 1
    expected = _GSTIN_CHECK_CHARS[(36 - (total % 36)) % 36]
    if checksum != expected:
        raise ValidationError("GSTIN checksum is invalid")
    return clean


def _pick(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalize_gst_payload(raw: dict[str, Any]) -> dict[str, str]:
    """Map common provider JSON shapes to party master fields."""
    nested = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    taxpayer = nested.get("taxpayerInfo") if isinstance(nested.get("taxpayerInfo"), dict) else nested
    source = taxpayer if isinstance(taxpayer, dict) else nested
    address_block = source.get("pradr") or source.get("primaryAddress") or source.get("address")
    if isinstance(address_block, dict):
        addr = _pick(address_block, "addr", "address", "fullAddress")
        if not addr and isinstance(address_block.get("addr"), dict):
            parts = address_block["addr"]
            addr = ", ".join(
                str(parts.get(k, "")).strip()
                for k in ("bno", "bnm", "st", "loc", "dst", "stcd", "pncd")
                if parts.get(k)
            )
    elif isinstance(address_block, str):
        addr = address_block.strip()
    else:
        addr = _pick(source, "address", "pradr", "primaryAddress")
    return {
        "legal_name": _pick(source, "lgnm", "legalName", "legal_name", "tradeNam", "trade_name"),
        "trade_name": _pick(source, "tradeNam", "trade_name", "lgnm", "legal_name"),
        "gstin": _pick(source, "gstin", "gstNo", "GSTIN"),
        "pan": _pick(source, "pan", "panNo", "PAN"),
        "address": addr,
        "city": _pick(source, "dst", "city", "location"),
        "state_code": _pick(source, "stcd", "stateCode", "state_code"),
        "pincode": _pick(source, "pncd", "pincode", "pin"),
        "status": _pick(source, "sts", "status", "gstinStatus"),
    }


def lookup_gstin_online(gstin: str, settings: dict[str, Any]) -> dict[str, str]:
    """Fetch taxpayer details using configured HTTP endpoint (AppyFlow-style or custom URL)."""
    normalized = validate_gstin(gstin)
    provider = str(settings.get("gst_lookup_provider") or "appyflow").strip().lower()
    api_key = str(settings.get("gst_lookup_api_key") or "").strip()
    if not api_key and provider != "custom":
        raise ValidationError(
            "Set GST lookup API key under Tools → Company Parameters (gst_lookup_api_key)."
        )
    if provider == "custom":
        template = str(settings.get("gst_lookup_url_template") or "").strip()
        if not template or "{gstin}" not in template:
            raise ValidationError(
                "Custom GST lookup requires gst_lookup_url_template with {gstin} placeholder."
            )
        url = template.replace("{gstin}", normalized)
    elif provider in {"sandbox", "gst_sandbox", "gov_sandbox"}:
        base = str(
            settings.get("gst_sandbox_base_url")
            or "https://sandbox.gst.gov.in/taxpayerapi/v1.0/authenticate"
        ).strip()
        template = str(settings.get("gst_lookup_url_template") or "").strip()
        if template and "{gstin}" in template:
            url = template.replace("{gstin}", normalized)
        elif "/search" in base or "{gstin}" in base:
            url = base.replace("{gstin}", normalized)
        else:
            url = (
                f"{base.rstrip('/')}/taxpayer/{normalized}"
                f"?api_key={urllib.parse.quote(api_key)}"
            )
    else:
        url = (
            "https://appyflow.in/api/v1/gst/verify"
            f"?key={urllib.parse.quote(api_key)}&gstNo={normalized}"
        )
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "AnajERP/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValidationError(f"GST lookup HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValidationError(f"GST lookup failed (check internet): {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError("GST lookup returned invalid JSON") from exc
    if isinstance(payload, dict) and payload.get("error"):
        raise ValidationError(str(payload.get("error")))
    if not isinstance(payload, dict):
        raise ValidationError("Unexpected GST lookup response")
    fields = normalize_gst_payload(payload)
    if not fields.get("legal_name") and not fields.get("trade_name"):
        raise ValidationError("GST lookup did not return a registered name for this GSTIN")
    fields["gstin"] = normalized
    return fields
