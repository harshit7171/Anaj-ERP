"""Real-time local bidding board state (master PC during mandi auctions)."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any


class AuctionBoardService:
    """In-memory lots with current bid — persisted only for the server process lifetime."""

    def __init__(self) -> None:
        self._guard = threading.RLock()
        self._lots: dict[str, dict[str, Any]] = {}

    def list_lots(self) -> list[dict[str, Any]]:
        with self._guard:
            rows = list(self._lots.values())
        rows.sort(key=lambda row: str(row.get("lot_no", "")))
        return rows

    def upsert_lot(self, payload: dict[str, Any]) -> dict[str, Any]:
        lot_no = str(payload.get("lot_no") or "").strip()
        if not lot_no:
            return {"ok": False, "error": "lot_no required"}
        lot_id = str(payload.get("lot_id") or lot_no)
        with self._guard:
            existing = self._lots.get(lot_id, {})
            row = {
                "lot_id": lot_id,
                "lot_no": lot_no,
                "commodity": str(payload.get("commodity") or existing.get("commodity") or ""),
                "mandi": str(payload.get("mandi") or existing.get("mandi") or ""),
                "quantity_qtl": float(payload.get("quantity_qtl") or existing.get("quantity_qtl") or 0),
                "status": str(payload.get("status") or existing.get("status") or "open"),
                "current_bid_rupees": float(
                    payload.get("current_bid_rupees")
                    if payload.get("current_bid_rupees") is not None
                    else existing.get("current_bid_rupees", 0)
                ),
                "bidder": str(payload.get("bidder") or existing.get("bidder") or ""),
                "updated_at": time.time(),
            }
            self._lots[lot_id] = row
            return {"ok": True, "lot": dict(row)}

    def place_bid(self, payload: dict[str, Any]) -> dict[str, Any]:
        lot_id = str(payload.get("lot_id") or payload.get("lot_no") or "").strip()
        if not lot_id:
            return {"ok": False, "error": "lot_id required"}
        amount = float(payload.get("bid_rupees") or 0)
        bidder = str(payload.get("bidder") or "").strip()
        if amount <= 0 or not bidder:
            return {"ok": False, "error": "bid_rupees and bidder required"}
        with self._guard:
            row = self._lots.get(lot_id)
            if row is None:
                row = {
                    "lot_id": lot_id,
                    "lot_no": str(payload.get("lot_no") or lot_id),
                    "commodity": str(payload.get("commodity") or ""),
                    "mandi": str(payload.get("mandi") or ""),
                    "quantity_qtl": float(payload.get("quantity_qtl") or 0),
                    "status": "open",
                    "current_bid_rupees": 0.0,
                    "bidder": "",
                    "updated_at": time.time(),
                }
            if float(row.get("current_bid_rupees") or 0) >= amount:
                return {"ok": False, "error": "Bid must exceed current price"}
            row["current_bid_rupees"] = amount
            row["bidder"] = bidder
            row["updated_at"] = time.time()
            row["status"] = "open"
            self._lots[lot_id] = row
            return {"ok": True, "lot": dict(row)}

    def close_lot(self, lot_id: str) -> dict[str, Any]:
        clean = str(lot_id or "").strip()
        with self._guard:
            row = self._lots.get(clean)
            if row is None:
                return {"ok": False, "error": "Unknown lot"}
            row["status"] = "closed"
            row["updated_at"] = time.time()
            return {"ok": True, "lot": dict(row)}

    def seed_demo_lots(self) -> None:
        if self._lots:
            return
        for lot_no, commodity, bid in (
            ("L-101", "Wheat", 2450),
            ("L-102", "Paddy", 1980),
            ("L-103", "Mustard", 6200),
        ):
            lot_id = str(uuid.uuid4())
            self.upsert_lot(
                {
                    "lot_id": lot_id,
                    "lot_no": lot_no,
                    "commodity": commodity,
                    "mandi": "Local APMC",
                    "quantity_qtl": 120,
                    "current_bid_rupees": bid,
                    "bidder": "—",
                    "status": "open",
                }
            )
