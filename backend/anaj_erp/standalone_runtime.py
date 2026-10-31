"""Single-PC runtime helpers (locks, auction board, local events)."""

from __future__ import annotations

from .auction_board import AuctionBoardService
from .document_locks import DocumentLockCoordinator
from .live_hub import LiveEventHub

lock_coordinator = DocumentLockCoordinator()
auction_board = AuctionBoardService()
live_hub = LiveEventHub()
