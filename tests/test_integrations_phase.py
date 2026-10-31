"""Document locks, cloud encryption, auction board (standalone)."""

from __future__ import annotations

from pathlib import Path

from anaj_erp.auction_board import AuctionBoardService
from anaj_erp.cloud_backup import decrypt_file
from anaj_erp.cloud_backup import encrypt_file
from anaj_erp.document_locks import DocumentLockCoordinator


def test_document_lock_conflict() -> None:
    locks = DocumentLockCoordinator(ttl_seconds=60)
    first = locks.acquire("doc:1", "user-a", "Munim A")
    second = locks.acquire("doc:1", "user-b", "Munim B")
    assert first["ok"] is True
    assert second["ok"] is False
    assert second.get("locked") is True
    locks.release("doc:1", "user-a")
    third = locks.acquire("doc:1", "user-b", "Munim B")
    assert third["ok"] is True


def test_encrypt_backup_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "sample.anajbackup"
    source.write_bytes(b"sqlite-backup-bytes")
    encrypted = encrypt_file(source, tmp_path / "out", "SecretPass123")
    assert encrypted.suffix == ".enc"
    restored = tmp_path / "restored.anajbackup"
    decrypt_file(encrypted, restored, "SecretPass123")
    assert restored.read_bytes() == source.read_bytes()


def test_auction_bid_must_increase() -> None:
    board = AuctionBoardService()
    board.upsert_lot({"lot_id": "L1", "lot_no": "101", "current_bid_rupees": 2000})
    low = board.place_bid({"lot_id": "L1", "bid_rupees": 1900, "bidder": "Buyer"})
    high = board.place_bid({"lot_id": "L1", "bid_rupees": 2100, "bidder": "Buyer"})
    assert low["ok"] is False
    assert high["ok"] is True
