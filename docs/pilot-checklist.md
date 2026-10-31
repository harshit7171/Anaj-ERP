# Phase 9 — Pilot & go-live checklist

Use this before parallel running with the legacy ERP or mandi books.

## A. Environment

- [ ] Office server PC: fixed IP, UPS, daily backup folder on D: or NAS
- [ ] `anaj-erp-server` running as scheduled task or service after reboot
- [ ] Firewall rule: LAN only, TCP 8765
- [ ] Each clerk laptop: WebView2, desktop build installed, LAN login tested
- [ ] Pakki and Kachi are **separate companies**; Kachi hidden for clerks verified

## B. Master data

- [ ] Parties, commodities, charge rules imported or entered
- [ ] Opening balances and opening stock for active financial year
- [ ] Prefix settings match legacy numbering where required

## C. Daily transactions (one week parallel)

- [ ] Cash book / journal entries match legacy totals
- [ ] Form-J / Form-I sample days reconciled
- [ ] Sale & purchase invoices: tax, mandi, commission lines match calculator
- [ ] Kachi purchase / mandi / GST purchase / lifting entries posted without error

## D. Reports

- [ ] Trial balance = legacy TB (or explained differences documented)
- [ ] GST register vs GSTR-1 JSON sample month
- [ ] Stock movement vs physical stock check (one commodity)

## E. Accountant sign-off

Complete [accountant-pilot-signoff.md](accountant-pilot-signoff.md) with name, date, and open items.

## F. Packaging

- [ ] `tools/build_release.ps1` completed on a clean VM
- [ ] Installer smoke: create company, post voucher, backup, restore to new company name
- [ ] License key installed on **server** installation ID

## G. Support

- [ ] Installation IDs recorded per site
- [ ] AnyDesk / support contact documented for April renewal
