# Secure release build pipeline (Phase 7 — Point 5)

Current shipping stack: **Vite + PyInstaller + Inno Setup** (pywebview desktop). Optional hardening layers:

| Stage | Tool | Status in repo |
|-------|------|----------------|
| UI minify | Vite production build | `npm run build` |
| UI obfuscation | `javascript-obfuscator` (optional) | Set `ANAJ_BUILD_OBFUSCATE=1` before build; see `vite.config.ts` |
| Python bytecode | PyInstaller `optimize=1` | `AnajERP.spec` |
| Node bytecode | Bytenode | Optional if migrating shell to Electron — not required for pywebview |
| Desktop pack | PyInstaller one-dir | `AnajERP.spec` |
| Electron pack | electron-builder | Future/alternate — document parity with `installer/` |
| Windows installer | Inno Setup 6 | `installer/AnajERP.iss` |
| Authenticode sign | `signtool` + EV/OV cert | `tools/sign_release.ps1` |

## One-command release (Windows)

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:ANAJ_CODE_SIGN_THUMBPRINT = "<cert-sha1-thumbprint>"  # optional
.\tools\build_release.ps1 -Version 0.1.0
```

## Code signing (SmartScreen)

1. Purchase a **Windows Code Signing Certificate** (OV/EV).
2. Install on the build machine.
3. Set `ANAJ_CODE_SIGN_THUMBPRINT` to the certificate SHA1 thumbprint.
4. `tools/sign_release.ps1` signs `AnajERP.exe` and verifies with `signtool verify`.

Unsigned builds run but may show SmartScreen on first install.

## Shortcuts (Point 17)

`installer/AnajERP.iss` creates **Start Menu** and optional **Desktop** shortcuts (`desktopicon` task, checked by default).

## Demo & licensing

Fresh installs receive **15 days demo** (`licensing.py`). After demo, posting is blocked until a signed key is installed. Vendor keys are issued via `tools/issue_license.py` or the fleet portal.
