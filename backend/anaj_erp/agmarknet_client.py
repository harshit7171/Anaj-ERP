"""Agmarknet / data.gov.in commodity modal prices (internet optional)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .errors import ValidationError

# data.gov.in Agmarknet daily prices resource (requires free API key from data.gov.in).
_DEFAULT_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"


def _normalize_row(record: dict[str, Any]) -> dict[str, str]:
    return {
        "state": str(record.get("state") or record.get("State") or ""),
        "district": str(record.get("district") or record.get("District") or ""),
        "market": str(record.get("market") or record.get("Market") or record.get("mandi") or ""),
        "commodity": str(
            record.get("commodity") or record.get("Commodity") or record.get("variety") or ""
        ),
        "modal_price": str(
            record.get("modal_price")
            or record.get("Modal_Price")
            or record.get("modal price")
            or record.get("price")
            or ""
        ),
        "min_price": str(record.get("min_price") or record.get("Min_Price") or ""),
        "max_price": str(record.get("max_price") or record.get("Max_Price") or ""),
        "price_date": str(record.get("arrival_date") or record.get("Price Date") or ""),
    }


def fetch_mandi_bhav(
    settings: dict[str, Any],
    *,
    state: str = "",
    commodity: str = "",
    limit: int = 40,
) -> dict[str, Any]:
    """Return mandi modal prices; uses cache-friendly HTTP when API key is configured."""
    api_key = str(settings.get("agmarknet_api_key") or settings.get("data_gov_api_key") or "").strip()
    resource_id = str(settings.get("agmarknet_resource_id") or _DEFAULT_RESOURCE).strip()
    if not api_key:
        return {
            "ok": True,
            "source": "offline_sample",
            "rows": _sample_rows(state, commodity, limit),
            "notice": "Set agmarknet_api_key in Company Parameters for live Agmarknet prices.",
        }
    filters: list[str] = []
    if state.strip():
        filters.append(f"state like '{state.strip()}'")
    if commodity.strip():
        filters.append(f"commodity like '{commodity.strip()}'")
    query = {
        "api-key": api_key,
        "format": "json",
        "limit": str(max(1, min(limit, 100))),
        "offset": "0",
    }
    if filters:
        query["filters[1]"] = " and ".join(filters)
    url = f"https://api.data.gov.in/resource/{resource_id}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "AnajERP/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValidationError(f"Agmarknet HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValidationError(f"Agmarknet fetch failed (check internet): {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError("Agmarknet returned invalid JSON") from exc
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        raise ValidationError("Unexpected Agmarknet response")
    rows = [_normalize_row(item) for item in records if isinstance(item, dict)]
    return {"ok": True, "source": "agmarknet", "rows": rows[:limit], "total": payload.get("total")}


def _sample_rows(state: str, commodity: str, limit: int) -> list[dict[str, str]]:
    samples = [
        {"state": "Haryana", "district": "Karnal", "market": "Karnal APMC", "commodity": "Wheat", "modal_price": "2450", "min_price": "2380", "max_price": "2510", "price_date": "today"},
        {"state": "Haryana", "district": "Panipat", "market": "Samalkha", "commodity": "Paddy", "modal_price": "1985", "min_price": "1920", "max_price": "2010", "price_date": "today"},
        {"state": "Punjab", "district": "Ludhiana", "market": "Khanna", "commodity": "Mustard", "modal_price": "6200", "min_price": "6100", "max_price": "6350", "price_date": "today"},
        {"state": "Rajasthan", "district": "Sri Ganganagar", "market": "Ganganagar", "commodity": "Cotton", "modal_price": "7120", "min_price": "7050", "max_price": "7200", "price_date": "today"},
    ]
    filtered = samples
    if state.strip():
        needle = state.strip().lower()
        filtered = [row for row in filtered if needle in row["state"].lower()]
    if commodity.strip():
        needle = commodity.strip().lower()
        filtered = [row for row in filtered if needle in row["commodity"].lower()]
    return filtered[: max(1, limit)]
