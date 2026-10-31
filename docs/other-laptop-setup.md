# Installing and Running Anaj ERP on Another Laptop

This guide covers a normal customer laptop and the optional second Home Laptop.

## Customer laptop requirements

- 64-bit Windows 10 or Windows 11
- At least 4 GB RAM; 8 GB recommended
- At least 2 GB free disk space plus space for company data and backups
- Microsoft Edge WebView2 Runtime
- Microsoft .NET Framework 4.8 or a supported current Windows .NET runtime
- A laser or inkjet printer for A4 bills, if printing is required
- A pen drive or external drive for backups

Python, Node.js, npm and Cursor are **not required** on a customer laptop when
using the packaged application.

## Before distributing the application

On the development/vendor laptop:

1. Open PowerShell in the project directory:

   ```powershell
   cd C:\A_Software
   ```

2. Build the React interface:

   ```powershell
   npm run build
   ```

3. Build the Windows application:

   ```powershell
   py -3.14 -m PyInstaller AnajERP.spec --clean --noconfirm
   ```

4. The portable application is produced in:

   ```text
   C:\A_Software\dist\AnajERP\
   ```

5. For a normal installer, install Inno Setup on the vendor laptop and compile:

   ```text
   C:\A_Software\installer\AnajERP.iss
   ```

   The generated setup file appears under the installer's `output` directory.

6. Code-sign the application and installer before customer distribution.
   Unsigned executables may be blocked by Windows SmartScreen, antivirus or
   corporate group policy.

Do not distribute the `tools` directory, source code or vendor private key.

## First installation on another laptop

1. Copy the signed setup file to the laptop.
2. Run the setup under the Windows user who will operate the software.
3. Select **Create a desktop shortcut**.
4. Launch **Anaj Accounting ERP** from the desktop.
5. The Lord Ganesha startup screen will appear.
6. Copy the displayed Installation ID or provide it to support through AnyDesk.
7. The vendor creates an annual license for that installation.
8. Paste the supplied key into **Annual Access Key Required** and select
   **Activate**.
9. Create a company and select the starting financial year.
10. Configure company details, accounts, parties, commodities and approved
    tax/expense rules.

Each Windows installation has a different Installation ID. A license issued for
one laptop does not activate another laptop.

## Issuing the annual license

Run this only on the protected vendor laptop:

```powershell
cd C:\A_Software
py -3.14 tools\license_admin.py issue `
  --installation-id "<customer-installation-id>" `
  --customer "Customer or Firm Name" `
  --start-year 2026 `
  --output "customer-2026.license"
```

Open the output file during the AnyDesk session, copy its content and paste it
into the customer's activation field.

The generated license is valid from April 1 of the selected year through April
30 of the following year. For example, `--start-year 2026` produces validity
from April 1, 2026 through April 30, 2027.

Never send or copy the vendor private-key file to a customer laptop.

## Moving existing company data to another laptop

Use this for disaster recovery or the initial Home Laptop setup.

### On the Office PC

1. Open the correct company and financial year.
2. Open **Configuration**.
3. Enter a safe path on the pen drive.
4. Select **Create Backup**.
5. Confirm that an `.anajbackup` file was created.
6. Safely eject the pen drive.

### On the Home Laptop

1. Install and activate Anaj ERP using that laptop's own Installation ID.
2. Insert the pen drive.
3. Open **Configuration**.
4. Select the `.anajbackup` file path.
5. Choose **Restore New Company**.
6. Return to the startup screen and select the restored company and year.

Restore will not overwrite an existing company. This protects live books from
accidental replacement.

## Standalone operation on each laptop

Anaj ERP is a **standalone offline desktop** application. There is no device
pairing or USB merge synchronization. To move data between machines, create a
fresh backup on the source laptop and **Restore New Company** on the target
laptop. Pakki and Dasti must remain separate companies with isolated databases.

## Updating the software

1. Take and verify a company backup before updating.
2. Close Anaj ERP.
3. Run the newer signed installer.
4. Do not delete the Windows user's AnajERP application-data folder.
5. Start the software and run **Reconciliation**.
6. Check company/year selection, Trial Balance, Commodity Balance and one bill
   preview before normal work continues.

Application files and accounting data are stored separately, so upgrading the
program does not require moving the company databases.

## Printer setup

1. Install the printer normally in Windows.
2. Set the desired printer as the default printer.
3. Save a test invoice as PDF.
4. Compare totals, margins and page breaks with the approved bill sample.
5. Use A4 paper and disable unexpected printer scaling when exact positioning
   is required.

## Backup recommendations

- Create a backup every working day.
- Keep at least three recent dated backups.
- Keep one backup on a separate pen drive or external disk.
- Test restoring into a separate test installation periodically.
- Never rely only on the Office PC and Home Laptop copies.

## Troubleshooting

### Application does not open

- Confirm Windows 10/11 is fully updated.
- Install or repair Microsoft Edge WebView2 Runtime.
- Install or repair Microsoft .NET Framework 4.8.
- Check Windows Defender, SmartScreen or company group-policy messages.
- Use a code-signed installer; do not disable security controls.

### License is rejected

- Confirm the key was issued for the Installation ID displayed on that laptop.
- Confirm the Windows date is correct.
- Confirm the requested financial-year license has not expired.
- Contact support for a controlled reissue after a genuine laptop replacement.

### USB package is rejected

- Confirm the package is being imported on the paired target device.
- Do not rename or modify package contents.
- Recopy the package to a healthy pen drive.
- Check whether the company was restored and paired correctly.

### Data or totals appear incorrect

- Confirm the active company and financial year in the title bar.
- Run **Reconciliation**.
- Review effective dates and bases of all tax/charge rules.
- Compare the entry with an accountant-approved golden example.
- Do not directly edit SQLite database files.

## Final production checklist

- Signed installer tested on a clean Windows laptop
- WebView2 and .NET prerequisites verified
- Customer-specific annual licenses tested
- Backup, restore and standalone company isolation tested
- Customer printer and A4 bill layout approved
- Haryana accountant has approved rates and ledger postings
- Opening balances reconcile with the previous software
- Trial Balance and Commodity Balance match the customer's source records
- Daily backup procedure demonstrated to the operator
