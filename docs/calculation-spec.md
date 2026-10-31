# Calculation specification

Money is stored as **integer paise**. Rounding uses half-up to paise at each charge line unless noted.

## Shared charge pipeline (`documents.py`)

1. Line amount: `amount_paise = round(rate_paise × quantity)` per line scale.  
2. Subtotal: sum of line amounts.  
3. Charges: effective-dated `charge_rule` rows for `transaction_type`, sorted by priority.  
4. Tax charges (`is_tax=1`) apply on configured basis (amount, bag, quantity).  
5. Grand total: subtotal ± non-tax charges ± tax per direction (`add` / `deduct`).  
6. Posted documents store charge snapshots on `document_charge` (immutable).

## Form - J (Parchi)

- Quantity: `(bags × pack_weight_kg) + loose_kg`, normalized to commodity `quantity_scale`.  
- Taxable value: sum of line amounts before bonus.  
- Bonus / commission: percentage or fixed rules from `charge_rule`.  
- Market fee / HRDF / association: mandi rules on amount or bags.  
- **Tests:** `tests/test_accounting_workflows.py`

## Sale invoice / Form - I (Dr.)

- Seeded defaults: DAMI, LABOUR, MARKET_FEE, SGST/CGST/IGST payable accounts (`database._seed_sale_bill_defaults`).  
- Multi-line GST from line metadata or document charges.  
- Credit limit preview before post (`credit.py`).

## Kachi / Mandi / GST purchase / Lifting

- Document types: `kachi_purchase`, `mandi_purchase`, `gst_purchase`, `lifting_entry`.  
- Use same charge engine; line fields from `DenseDocumentForm` configs.  
- Stock: `inventory_movement` on post when document type requires it.

## Registers & interest

- Trial balance / ledger: sum `voucher_line` by account.  
- Simple interest: `reports.calculate_simple_interest` on ledger balance × days × rate.

Accountant must sign off Haryana rate bundles before production (see `docs/accountant-pilot-signoff.md`).
