# Miracle / Aarath / Marg parity audit

**Menu leaves detected:** 102

## Reference checklist

### Miracle Mandi
- [partial] Form-J farmer patti deductions (tula, cleaning, advance)
- [partial] Form-I buyer invoice cess & commission
- [partial] F2–F12 keyboard shortcuts
- [partial] Gate pass / auction / lifting chain
- [partial] Munim LAN posting

### Aarath
- [partial] Kachi vs pakki arhat modes
- [partial] Bardana tracking
- [partial] Interest on farmer advances
- [implemented] Rokad cash book vs physical drawer

### Marg ERP
- [partial] GST GSTR-1 / 3B exports
- [partial] TDS/TCS turnover alerts
- [partial] Multi-user RBAC
- [partial] Backup & restore

## Implementation map

```json
{
  "Form-J": "DenseDocumentForm Form - J",
  "Form-I": "DenseDocumentForm Form - I",
  "shortcuts": "App.tsx shortcuts",
  "LAN": "lan_server.py",
  "GST": "report_catalog gstr1_json",
  "cash drawer": "cash_drawer_reconciliation report"
}
```

Regenerate: `python tools/run_parity_audit.py`
