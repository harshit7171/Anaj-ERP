# Offline Anaj Accounting ERP

Keyboard-first Windows accounting software for Haryana grain commission agents.
The application uses React inside pywebview, Python domain services and isolated
SQLite company databases. It does not require a cloud service.

## Current implementation

- Windows desktop backend entry point
- installation identity and catalog database
- isolated company databases
- company and April-March financial-year startup selection
- editable historical-year model with lock metadata
- fixed-point money, deterministic charge rules and balanced voucher validation
- accounts, parties, commodities, effective rules, vouchers and audit outbox
- Form-J, Form-I, sale/purchase/challan document engine and inventory movements
- trial balance, ledgers, registers, stock, GST/TDS/mandi and interest reports
- A4 PDF invoices with stored charge breakdowns
- signed annual licensing for standalone offline desktop use
- farmer credit limits, charge-rule administration, and compliance reminders
- screenshot-inspired startup, autocomplete and keyboard-first entry UI

See [the accounting specification](docs/accounting-spec.md) for the complete
target modules and required accountant approvals. See the
[operator guide](docs/operator-guide.md) for daily workflows.

## Development setup

Requirements:

- Python 3.11 or newer
- Node.js LTS
- Microsoft Edge WebView2 Runtime (normally included with supported Windows)

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm install
```

Run the React interface for browser development:

```powershell
npm run dev
```

Run the complete desktop application in development:

```powershell
$env:ANAJ_ERP_DEV_URL = "http://127.0.0.1:5173"
anaj-erp
```

Build and run locally:

```powershell
npm run build
anaj-erp
```

The source-tree desktop launch enforces annual licensing. Generate the
vendor-only key pair once on the vendor machine:

```powershell
py -3.14 tools\license_admin.py init --public resources\license_public_key.pem
```

The protected private key is stored outside the repository. Issue a key using
the installation ID shown on the customer's activation screen:

```powershell
py -3.14 tools\license_admin.py issue `
  --installation-id "<installation-id>" `
  --customer "Customer Name" `
  --start-year 2026 `
  --output customer-2026.license
```

Never distribute the vendor private key or include `tools/license_admin.py` in
the customer installer.

## Office LAN server (multi-user)

Shared SQLite on one office PC; laptops use **Office server (LAN)** on the startup screen.

```powershell
pip install -e ".[server]"
$env:ANAJ_ERP_ADMIN_PASSWORD = "YourBootstrapPassword"
anaj-erp-server
```

See [docs/lan-server-setup.md](docs/lan-server-setup.md).

## Pilot & release

- Checklist: [docs/pilot-checklist.md](docs/pilot-checklist.md)
- Automated smoke: `python tools/pilot/smoke_pilot.py`
- Full build script: `tools/build_release.ps1`

## Windows release build

```powershell
npm run build
py -3.14 -m PyInstaller AnajERP.spec --clean --noconfirm
```

Compile `installer\AnajERP.iss` with Inno Setup to create an installer that adds
Start Menu and optional desktop shortcuts. Code-sign the executable and
installer before customer distribution.

## Verification

```powershell
ruff check .
ruff format --check .
mypy backend
pytest
npm run build
```

## Data location

Production data is stored under the current Windows user's roaming application
data directory in `AnajERP`. Company databases are never placed inside the
program installation folder.

Do not use this build for production books until Haryana statutory rates,
voucher postings, invoice layouts and accountant golden examples are reviewed
and approved.
