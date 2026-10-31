# Competitive features (desktop implementation)

## Implemented now

| Feature | Where |
|---------|--------|
| WhatsApp share (J/I/Invoice/reminder text) | **WhatsApp** on posted dense forms; opens `wa.me` in browser |
| Bulk reminder letters PDF | **Tools → Reminder Letters** |
| Broker commission report | **Reports 1 → Broker Commission Report** |
| Item-wise profitability | **Reports 1 → Item-Wise Profitability** |
| Blended average cost | **Tools → Blended Cost Calculator** + report with item filter |
| Executive dashboard | Home dashboard cards (arrivals, cash, dues, banks, TCS alerts) |
| Fast Kachi / Lifting | **Daily** menu ⚡ entries |
| Bank CSV reconciliation | **Tools → Bank Reconciliation** |
| Clause 44 export JSON | **GST Reports → Clause 44 Tax Audit Export** |
| Cover / envelope PDF | **Tools → Cover Printing** |
| Document attachments | API `attach_document_file` / schema `document_attachment` (UI hook via API) |
| TCS ₹50L threshold alerts | Dashboard **Tax Threshold Alerts** |

## Future (needs WhatsApp Business API / cloud)

- Official WhatsApp Business API with delivery receipts and templates  
- Automated bulk WhatsApp without opening the browser  
- Email SMTP for reminders  

Configure party **phone** numbers (10-digit) for WhatsApp links to pre-fill the correct chat.

## GST auto-fill (internet)

- **Tools → Company Parameters**: set `gst_lookup_api_key` (e.g. AppyFlow).
- **Account Master / Transport Master**: enter GSTIN → **Fetch** fills name, address, PAN.

## Google Drive backup (optional)

- **Tools → Settings → Google Drive Backup**: sync folder and/or service-account upload.
- **Tools → Backup** copies to sync folder when enabled; API upload needs `pip install anaj-erp[integrations]`.

## Menus & user rules

- **Master / Daily / Entry / Search / Reports / Tools** use hover **›** submenus (Add / Modify) like the reference ERP.
- **Tools → User Alerts & WhatsApp**: TDS/TCS popups, credit limit, WhatsApp defaults.
- **Find Account**: **Remind** sends WhatsApp payment reminder when enabled.
