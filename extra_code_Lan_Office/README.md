# Archived LAN / office multi-PC code

This folder preserves the **office LAN server**, **remote RPC client**, and **multi-user** pieces removed from the default standalone build.

## Contents

| Path | Purpose |
|------|---------|
| `backend/lan_server.py` | FastAPI LAN RPC + WebSocket server |
| `backend/lan_*.py` | Discovery, auth, locks, session, runtime |
| `backend/run_server_entry.py` | Packaged server entry |
| `run_server.py` | `anaj-erp-server` launcher |
| `frontend/remoteApi.ts` | Browser LAN client (`installRemoteApiBridge`) |
| `tests/test_lan_api.py` | LAN integration tests |
| `docs/lan-server-setup.md` | Setup notes |

## Restoring LAN mode (developers)

1. Copy modules back under `backend/anaj_erp/`.
2. Restore `frontend/src/api/remoteApi.ts` and wire `App.tsx` connection mode.
3. Install server extras: `pip install -e ".[server]"`.
4. Run `python run_server.py` on the master PC.

The production desktop app is **single-PC standalone** only; data lives under the local data directory with optional user-configured cloud/sync backup paths.
