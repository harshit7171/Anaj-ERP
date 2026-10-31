export type ReportSpec = {
  reportKey: string;
  needsDates?: boolean;
  needsAccount?: boolean;
  needsCommodity?: boolean;
  kachiOnly?: boolean;
  jsonExport?: boolean;
  needsPhysicalCash?: boolean;
  agingAsOf?: boolean;
  needsGroup?: boolean;
  needsRate?: boolean;
  asOfDate?: boolean;
  interestMode?: string;
};

/** Window title → catalog report key and parameter requirements. */
export const reportByTitle: Record<string, ReportSpec> = {
  "Day Book": { reportKey: "day_book", needsDates: true },
  "Cash Book Report": { reportKey: "cashbook", needsDates: true, needsAccount: true },
  "Account Ledger": { reportKey: "ledger", needsDates: true, needsAccount: true },
  "Profit & Loss": { reportKey: "profit_loss", needsDates: true },
  "Balance Sheet": { reportKey: "balance_sheet", needsDates: true },
  "Sale Register": { reportKey: "sale_register", needsDates: true },
  "Purchase Register": { reportKey: "purchase_register", needsDates: true },
  "Form - J Register": { reportKey: "jform_list", needsDates: true },
  "Form - I Register": { reportKey: "iform_list", needsDates: true },
  "Due Date Report": { reportKey: "due_date_report", needsDates: true },
  "Pending Bills": { reportKey: "pending_bills", needsDates: true },
  "Stock Movement Register": { reportKey: "stock_register", needsDates: true },
  "Kachi Stock Register": { reportKey: "stock_register", needsDates: true, kachiOnly: true },
  "Kachi Purchase Report": { reportKey: "kachi_purchase_report", needsDates: true },
  "Mandi Purchase Report": { reportKey: "mandi_purchase_report", needsDates: true },
  "Lifting Report": { reportKey: "lifting_report", needsDates: true },
  "Market Fees Report": { reportKey: "market_fees", needsDates: true },
  "TDS Report": { reportKey: "tds_report", needsDates: true },
  "GST Purchase Detail": { reportKey: "gst_purchase_detail", needsDates: true },
  "GST Purchase / Sale Summary": { reportKey: "gst_purchase_sale_summary", needsDates: true },
  "HSN Wise Summary": { reportKey: "hsn_wise_summary", needsDates: true },
  "Bill Wise GST (Sale)": { reportKey: "bill_wise_gst_sale", needsDates: true },
  "Bill Wise GST (Purchase)": { reportKey: "bill_wise_gst_purchase", needsDates: true },
  "GSTR-1 JSON Export": { reportKey: "gstr1_json", needsDates: true, jsonExport: true },
  "GSTR-3B Summary": { reportKey: "gstr3b_summary", needsDates: true },
  "Month Item Wise (Sale)": { reportKey: "month_item_wise_sale", needsDates: true },
  "Month Item Wise (Purchase)": { reportKey: "month_item_wise_purchase", needsDates: true },
  "Broker Commission Report": { reportKey: "broker_commission", needsDates: true },
  "Item-Wise Profitability": { reportKey: "item_wise_profitability", needsDates: true },
  "Clause 44 Tax Audit Export": { reportKey: "clause_44_tax_audit", needsDates: true, jsonExport: true },
  "Blended Average Cost Report": {
    reportKey: "blended_average_cost",
    needsDates: true,
    needsCommodity: true,
  },
  "Bardana Report": { reportKey: "stock_register", needsDates: true },
  "Talpat Report": { reportKey: "due_date_report", needsDates: true },
  "Farmer Seasonal Turnover": { reportKey: "farmer_seasonal_turnover", needsDates: true },
  "Buyer Payment Aging": { reportKey: "buyer_payment_aging", needsDates: true, agingAsOf: true },
  "Mandi Cess M-Form Summary": { reportKey: "mandi_cess_m_form", needsDates: true },
  "Daily Cash Drawer Reconciliation": {
    reportKey: "cash_drawer_reconciliation",
    needsDates: true,
    needsAccount: true,
    needsPhysicalCash: true,
  },
  "Expense Wise Purchase Detail": { reportKey: "purchase_register", needsDates: true },
  "Debit Note Report": { reportKey: "debit_note_report", needsDates: true },
  "Credit Note Report": { reportKey: "credit_note_report", needsDates: true },
  Cashbook: { reportKey: "cashbook", needsDates: true, needsAccount: true },
  Ledger: { reportKey: "ledger", needsDates: true, needsAccount: true },
  "Combined Ledger": { reportKey: "ledger", needsDates: true, needsAccount: true },
  "Trial Balance": { reportKey: "trial_balance" },
  "Trial Balance Difference Report": { reportKey: "trial_balance_difference" },
  "Account Balances Under a Group": {
    reportKey: "account_balances_by_group",
    needsGroup: true,
  },
  "Cash in Hand Report": { reportKey: "cash_in_hand", needsDates: true, asOfDate: true },
  "Trading & I and Balance Sheet": { reportKey: "trading_pl_balance_sheet" },
  "Commodity Balance": { reportKey: "stock_balance" },
  "GST Register": { reportKey: "gst_register", needsDates: true },
  "Crop Sale Report(Kachi Aarat)": { reportKey: "kachi_purchase_report", needsDates: true },
  "JForm List": { reportKey: "jform_list", needsDates: true },
  "Stock Register": { reportKey: "stock_register", needsDates: true },
  "Stock Register (Kachi)": { reportKey: "stock_register", needsDates: true, kachiOnly: true },
  "Bill Wise Pending Balance": { reportKey: "pending_bills", needsDates: true },
  "Lifting Summary (Veh-Challan) Wise Report": { reportKey: "lifting_report", needsDates: true },
  "Bill Wise Purchase Detail": { reportKey: "purchase_register", needsDates: true },
  "Bill Wise Sale Detail": { reportKey: "sale_register", needsDates: true },
  "Bill Wise Sale Register": { reportKey: "sale_register", needsDates: true },
  "Bill Wise Purchase Register": { reportKey: "purchase_register", needsDates: true },
  "I-Form (From J-Form) List": { reportKey: "iform_list", needsDates: true },
  "Purchase & Sale Summary": { reportKey: "gst_purchase_sale_summary", needsDates: true },
  "Bill Wise Sale Detail(GST)": { reportKey: "bill_wise_gst_sale", needsDates: true },
  "Month Wise Item Wise Sale Report": { reportKey: "month_item_wise_sale", needsDates: true },
  "Month Wise Item Wise Purchase Report": { reportKey: "month_item_wise_purchase", needsDates: true },
  "Gst Purchase Detail": { reportKey: "gst_purchase_detail", needsDates: true },
  "Form GSTR-1(Govt)": { reportKey: "gstr1_json", needsDates: true, jsonExport: true },
  "GST Debit/Credit Note Report": { reportKey: "gst_dn_cn_report", needsDates: true },
  "HSN Wise Sale/Purchase Summary": { reportKey: "hsn_wise_summary", needsDates: true },
  "Form GSTR-3B2 Fill": { reportKey: "gstr3b_summary", needsDates: true },
  "GSTR-2B Report Auto": { reportKey: "gstr2b_report", needsDates: true },
  "ITC Reversed & Claimed Report": { reportKey: "itc_reversed_report", needsDates: true },
  "ITC Availed Report (Capital Goods & Services)": { reportKey: "itc_availed_report", needsDates: true },
  "Report GSTR-9": { reportKey: "gstr9_report", needsDates: true },
  "Interest Statements": { reportKey: "interest_statement", needsDates: true, needsRate: true, interestMode: "simple" },
  "Direct Interest": { reportKey: "interest_statement", needsDates: true, needsRate: true, interestMode: "simple" },
  "Balancing Method Interest": {
    reportKey: "interest_statement",
    needsDates: true,
    needsRate: true,
    interestMode: "compound",
  },
  "Mandi Dhara Interest": {
    reportKey: "interest_statement",
    needsDates: true,
    needsRate: true,
    interestMode: "simple",
  },
  "Balancing Method Interest (Combined)": {
    reportKey: "interest_statement",
    needsDates: true,
    needsRate: true,
    interestMode: "compound",
  },
  Interest: { reportKey: "interest_statement", needsDates: true, needsAccount: true, needsRate: true, interestMode: "simple" },
};

export function resolveReportSpec(menuTitle: string, screen: string): ReportSpec | undefined {
  return reportByTitle[menuTitle] ?? reportByTitle[screen];
}

export const reportsMenu1 = [
  "Day Book",
  "Cash Book Report",
  "Account Ledger",
  "Profit & Loss",
  "Balance Sheet",
  "Sale Register",
  "Purchase Register",
  "Form - J Register",
  "Form - I Register",
  "Due Date Report",
  "Pending Bills",
  "Stock Movement Register",
  "Kachi Stock Register",
  "Kachi Purchase Report",
  "Mandi Purchase Report",
  "Lifting Report",
  "Market Fees Report",
  "TDS Report",
  "Trial Balance",
  "Commodity Balance",
  "Interest",
  "Broker Commission Report",
  "Item-Wise Profitability",
  "Clause 44 Tax Audit Export",
  "Farmer Seasonal Turnover",
  "Buyer Payment Aging",
  "Mandi Cess M-Form Summary",
  "Daily Cash Drawer Reconciliation",
];

export const gstReportsMenuExtra = ["Clause 44 Tax Audit Export"];

export const reportsMenu2 = [
  "GST Register",
  "GST Purchase Detail",
  "GST Purchase / Sale Summary",
  "HSN Wise Summary",
  "Bill Wise GST (Sale)",
  "Bill Wise GST (Purchase)",
  "GSTR-1 JSON Export",
  "GSTR-3B Summary",
  "Month Item Wise (Sale)",
  "Month Item Wise (Purchase)",
];

export const searchMenuItems = [{ label: "Find Account", window: "Find Account" }];

export const toolsMenuItems = [
  { label: "Find Account", window: "Find Account" },
  { label: "Stock Adjustment", window: "Stock Adjustment" },
  { label: "Company Parameters", window: "Company Parameters" },
  { label: "Prefix Settings", window: "Prefix Settings" },
  { label: "Backup & Administration", window: "Configuration" },
  { label: "Office Users", window: "Office Users" },
  { label: "System Diagnostics", window: "System Diagnostics" },
  { label: "Merge Parties", window: "Merge Parties" },
  { label: "Bank Reconciliation", window: "Bank Reconciliation" },
  { label: "Reminder Letters", window: "Reminder Letters" },
  { label: "Cover Printing", window: "Cover Printing" },
  { label: "Blended Cost Calculator", window: "Blended Cost Calculator" },
];

export const fastEntryMenu = [
  { label: "Fast Kachi Purchase", window: "Fast Kachi Purchase" },
  { label: "Fast Lifting Entry", window: "Fast Lifting Entry" },
];

export const registersMenu = [
  "Sale Register",
  "Purchase Register",
  "Form - J Register",
  "Form - I Register",
  "Kachi Purchase Report",
  "Mandi Purchase Report",
  "GST Register",
  "Stock Movement Register",
];

export const printMenu = [
  { label: "Print Day Book (PDF)", window: "__print_day_book__" },
  { label: "New Sale Invoice", window: "Sale Invoice" },
];

export function isCatalogReport(title: string, screen?: string): boolean {
  if (title in reportByTitle) return true;
  if (screen && screen in reportByTitle) return true;
  return false;
}
