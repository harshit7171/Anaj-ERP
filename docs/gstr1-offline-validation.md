# GSTR-1 — GST Offline Utility validation

Anaj ERP exports GSTR-1 JSON with `version: GST3.1.4` and runs the same structural checks as `validate_gstr1_offline_utility()` before export when **Validate for offline tool** is enabled on **Form GSTR-1 JSON**.

## Automated checks (CI)

- `tests/test_gstr1_export.py` — GSTIN, fp, HSN vs outward totals
- `tests/test_gstr1_offline_rules.py` — required sections, idt/pos/itms, HSN length

Backend RPC: `validate_gstr1_offline_json` with `json_text` or `file_path`.

## Manual — official GST Offline Utility

1. Download **GST Offline Tool** (GSTR-1) from [GST portal downloads](https://www.gst.gov.in/download/returns).
2. In ERP: **GST Reports → Form GSTR-1 JSON**, set dates, enable validation, export/save JSON.
3. Open the utility → Import → select the JSON file.
4. Fix any utility errors in `gstr1_export.py` / `gstr1_schema.py` / `gstr1_validate.py` until import shows **zero validation errors**.

Re-run `py -m pytest tests/test_gstr1_export.py tests/test_gstr1_offline_rules.py` after schema changes.
