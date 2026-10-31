# Office LAN server (Phase 8)

Run one **Anaj ERP server** on the office PC. All staff connect with the desktop app in **Office server (LAN)** mode. Data stays in the same SQLite catalog and company files on that PC.

## Install server dependencies

```powershell
pip install -e ".[server]"
```

## First-time bootstrap admin

Set a one-time admin password before starting the server (creates user `admin` if no users exist):

```powershell
$env:ANAJ_ERP_ADMIN_PASSWORD = "Choose-A-Strong-Password"
$env:ANAJ_ERP_DATA_DIR = "D:\AnajERP\shared-data"   # optional; default is roaming AppData
anaj-erp-server
```

Or:

```powershell
py -3.14 run_server.py
```

Listen address defaults to `0.0.0.0:8765`. Open Windows Firewall for TCP 8765 on the office LAN.

## Client laptops

1. Install the normal Anaj ERP desktop build.
2. On the company selection screen, choose **Office server (LAN)**.
3. Enter `http://<office-pc-ip>:8765`, sign in as Munim/clerk user.

## Roles

| Role | Access |
|------|--------|
| admin | Users, company Kachi flag, all writes |
| munim | Post vouchers/documents, reports, tools |
| operator | Writes (no user admin) |
| clerk / readonly | Read + reports only |

Users without **Can view Kachi** do not see companies marked `kachi` in the catalog.

## Licensing

The **office server PC** holds the annual license. LAN clients rely on the server `health` / `license_status` response.

## Security notes

- Use a strong admin password; change default bootstrap immediately.
- Restrict server to trusted office LAN; do not expose port 8765 to the public internet.
- Back up `ANAJ_ERP_DATA_DIR` (catalog + `companies\`) daily via **Tools → Backup**.
