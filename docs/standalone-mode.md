# Standalone single-PC mode

The desktop ERP is optimized for **one Windows PC** with **multiple local companies** (separate SQLite databases under the configured data directory).

## Data storage

- All transactional data is stored **locally** by default.
- Use **Tools → Configuration / backup** to set `default_backup_path` and create `.anajbackup` packages on disk.

## Optional cloud copy

Cloud features are **opt-in** via company settings:

| Setting | Effect |
|---------|--------|
| `google_drive_sync_folder` | Copies each backup into a local folder (e.g. Google Drive for desktop) |
| `google_drive_enabled` + service account | Uploads backup to Drive when configured |
| `cloud_backup_on_exit` + passphrase | Encrypted exit backup only when explicitly enabled |

If these are empty/disabled, the app runs fully offline with no cloud prompts.

## Archived LAN / office sharing

Multi-PC LAN server, remote RPC client, and office user admin live in **`extra_code_Lan_Office/`**. See that folder’s README to restore LAN mode for development.
