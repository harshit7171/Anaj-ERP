# Anaj ERP Accounting and Workflow Specification

Status: implementation baseline; statutory rates and posting examples require
sign-off by a Haryana mandi accountant before production use.

## Operating model

- The product is an offline Windows accounting system for Haryana grain
  commission agents and traders.
- A company database contains multiple April-March financial years. Operators
  select company and year at startup. Previous years remain editable unless an
  administrator locks them; reopening is audited.
- Amounts are stored in paise. Quantities and weights are fixed-point values
  with explicit commodity scales. Posted history is never recalculated from
  current tax rules.
- Draft documents may be corrected. Posted financial or inventory events use a
  reversal/replacement workflow, preserving the audit trail.

## Module inventory

### Startup and administration

- Lord Ganesha welcome screen
- Create, open and archive company
- Select, create, lock and audited-reopen financial year
- Company details, numbering series, printer and bill-template configuration
- Local users/roles, annual signed license, backup, restore and integrity check
- Standalone per-machine operation; backup/restore for disaster recovery

### Masters

- Parties: farmer, purchaser, supplier, customer, commission agent and
  transporter
- Ledgers and chart of accounts
- Commodity, variety, HSN, quantity scale, bag type and standard bag weight
- Warehouse, location, route, vehicle and transporter
- Expense/charge, GST, TDS, APMC/mandi, HRDF/cess, labour/jhadhai, bardana and
  commission rules
- Opening account, party, commodity, lot and bag balances

### Entry and vouchers

- F2 Cash Book: receipts and payments with cash-in-hand
- F3 Journal: balanced debit and credit lines
- F4 Form-J: farmer purchase/settlement
- F5 Form-I debit and F11 Form-I credit
- Sale bill/invoice and purchase bill/invoice
- Receipt, payment, contra and general accounting voucher
- Debit note, credit note, sale memo and purchase memo
- Delivery challan, transfer challan/invoice and gate pass
- Self-purchase and commodity-transfer account
- Consignment debit/credit, inward/outward and milling flows
- Stock adjustment, warehouse transfer and packing-material transfer
- “Purchase Muttax” remains a reference-menu label until its exact local
  business meaning and postings are confirmed.

### Registers and reports

- Day book, Cash Book, Journal register and voucher registers
- Account ledger/balance, party balance and outstanding ageing
- Commodity, lot, warehouse and bag balances
- Trial balance, profit and loss and balance sheet
- Interest calculation and register
- Purchase, sales, Form-J and Form-I registers
- GST sales/purchase/HSN/tax summaries and offline filing worksheets
- TDS register and summaries
- APMC/market fee, HRDF/cess and Haryana mandi summaries
- Print, PDF and export views with ledger/document drill-down

## Keyboard workflow

1. Focus starts in the first required field.
2. Typing opens case-insensitive prefix/token matches. For example, `HA`
   displays matching parties, accounts or commodities.
3. Up/Down changes the highlighted result. Enter or click accepts it and moves
   to the next field. Exact matches are accepted directly.
4. Tab/Shift+Tab move forward/back. Esc closes lookup or exits the active
   window after confirmation. Function keys open the displayed shortcut.
5. Unmatched master text is not silently saved. Authorized users can create a
   master through a quick dialog and return to the original entry.
6. Grids use Enter-to-next-cell and Enter-at-row-end to validate/add a row.
   Validation returns focus to the first invalid field.

## Quantities, bags and rates

Each invoice line preserves:

- entered bags
- packing/standard bag weight
- extra or loose quantity
- normalized quantity/weight
- rate and rate basis
- line amount

The commodity defines quantity scale and optional standard bag weight. Source
values are retained so printed and audited figures do not change when the
commodity master changes.

Example normalization (configuration-dependent):

```text
normalized_weight = (bags × configured_bag_weight) + loose_weight
line_value = round(normalized_rate_quantity × rate, configured_rounding)
```

The rate quantity (quintal, kilogram, unit, bag, etc.) must be explicit. No
implicit `50 kg` assumption is permitted.

## Effective-dated calculation rules

Rules resolve by company, transaction type, party/party class, commodity and
document date. A more-specific rule overrides a general rule. Priority breaks
ties. Each rule records:

- printed label and internal code
- percentage or fixed mode
- amount, bag, quantity or weight basis
- rate, minimum, maximum and rounding mode
- addition/deduction direction
- taxable/inclusive behavior and ordering
- debit/credit ledger mapping
- effective-from/effective-to dates

Percentage rule:

```text
charge_paise = round(basis_paise × percentage / 100)
```

Fixed per-unit rule:

```text
charge_paise = round(units × rupees_per_unit × 100)
```

Calculation order:

1. Normalize line quantities, bags and weights.
2. Calculate line/value total.
3. Apply ordered mandi/APMC, HRDF/cess, market, labour/jhadhai,
   bardana/bagging, association/auction and other expenses.
4. Apply discount or bonus.
5. Determine GST taxable basis and calculate CGST/SGST or IGST as configured.
6. Calculate commission and freight at their configured stage.
7. Calculate TDS/deductions on the legally configured basis.
8. Round only at configured boundaries.
9. Produce grand total and balanced proposed ledger entries.

Automatic values may be overridden only by an authorized operator with a
reason. The rule, basis, automatic amount, overridden amount, user, device and
time become part of the posted calculation snapshot.

No percentage visible in a screenshot is treated as a statutory default.
Initial rates require dated Haryana source material and accountant-approved
golden examples.

## Double-entry posting requirements

- Every posted voucher has at least two lines and equal debit/credit totals.
- Voucher numbers are unique by financial year, voucher type and series.
- Invoice, charge, tax and inventory posting occurs in one SQLite transaction.
- Form-J, Form-I, sales, purchase, receipt, payment and journal mappings each
  require a signed-off example showing expected ledgers and amounts.
- Locked periods reject posting. Reopening records who, when and why.
- A reversal references the original event and posts equal opposite movements.

## Bill and print requirements

The supplied A4 commission-agent bill defines these configurable regions:

- Original/Duplicate/Triplicate heading
- company name, business type, address, jurisdiction, GSTIN, PAN, phones
- bill-to and ship-to name/address/GSTIN/PAN/state code
- invoice number/date/time, from/to, bags, PO, due date and payment status
- vehicle, driver, GR and e-way bill
- commodity/description, HSN, bags, weight/quantity, rate and line amount
- ordered VALUE/expense/mandi/market/HRDF/labour/bundling/freight/commission/tax
  rows
- total bags, weight, value, expenses, taxes and grand total
- amount in words, interest/payment terms, average rates, bank/IFSC, E.&O.E.,
  seal and authorized signature

Preview and PDF must match A4 laser/inkjet output. Every printed charge traces
to a stored charge line. Golden PDF comparison tolerances must cover font
metrics while requiring exact text and monetary values.

## Required approval examples

Before production, an accountant must provide and approve at least:

1. Form-J purchase with standard bags, loose quantity and farmer settlement.
2. Form-I debit and credit examples.
3. Sale invoice with two commodity lots and the supplied bill expense layout.
4. APMC/mandi, HRDF/cess, labour kacchi/pakki or jhadhai and commission cases.
5. Intra-state GST and inter-state GST examples.
6. TDS threshold/basis example and reversal.
7. Cash receipt/payment, journal correction and interest calculation.
8. Stock transfer, packing material and year-opening/closing balances.
9. Expected trial balance, commodity balance, GST/TDS and mandi reports.

Until these are signed off, calculations are testable software behavior but
must not be represented as legally certified Haryana accounting treatment.
