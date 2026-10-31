"""Shared LAN master runtime (locks, auction board, live events)."""

from __future__ import annotations

from .auction_board import AuctionBoardService
from .lan_discovery import DiscoveryBroadcaster
from .lan_locks import LanLockCoordinator
from .live_hub import LiveEventHub

lock_coordinator = LanLockCoordinator()
auction_board = AuctionBoardService()
live_hub = LiveEventHub()
discovery_broadcaster: DiscoveryBroadcaster | None = None
