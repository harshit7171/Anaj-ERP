export type ScreenMode = "add" | "modify";

export type ResolvedWindow = {
  screen: string;
  mode?: ScreenMode;
};

const SCREEN_ALIASES: Record<string, string> = {
  "J Form (Parchi)": "Form - J",
  "I Form (Auction Bill)": "Form - I (Dr.)",
  "I Form Lifting Entry": "Lifting Entry",
  "Accounting Reports": "__accounting_reports__",
  "Opening Bank Master": "Bank Master",
  "Closing Bank Master": "Bank Master",
  "Opening Stock Entry": "Stock Entry Master",
  "Closing Stock Entry": "Stock Entry Master",
  Cashbook: "Cash Book Report",
  Ledger: "Account Ledger",
  "Trading & I and Balance Sheet": "Profit & Loss",
  "Account Balances Under a Group": "Trial Balance",
  "Cash in Hand Report": "Cash Book Report",
  "Trial Balance Difference Report": "Trial Balance",
  "Combined Ledger": "Account Ledger",
  "Interest Statements": "Interest",
  "Direct Interest": "Interest",
  "Balancing Method Interest": "Interest",
  "Mandi Dhara Interest": "Interest",
  "Balancing Method Interest (Combined)": "Interest",
  "JForm List": "Form - J Register",
  "Stock Register": "Stock Movement Register",
  "Stock Register (Kachi)": "Kachi Stock Register",
  "Bill Wise Pending Balance": "Pending Bills",
  "Lifting Summary (Veh-Challan) Wise Report": "Lifting Report",
  "Bill Wise Purchase Detail": "Purchase Register",
  "Bill Wise Sale Detail": "Sale Register",
  "Bill Wise Sale Register": "Sale Register",
  "Bill Wise Purchase Register": "Purchase Register",
  "I-Form (From J-Form) List": "Form - I Register",
  "Crop Sale Report(Kachi Aarat)": "Kachi Purchase Report",
  "Purchase & Sale Summary": "GST Purchase / Sale Summary",
  "Bill Wise Sale Detail(GST)": "Bill Wise GST (Sale)",
  "Month Wise Item Wise Sale Report": "Month Item Wise (Sale)",
  "Month Wise Item Wise Purchase Report": "Month Item Wise (Purchase)",
  "Gst Purchase Detail": "GST Purchase Detail",
  "Form GSTR-1(Govt)": "GSTR-1 JSON Export",
  "GST Debit/Credit Note Report": "GST Register",
  "HSN Wise Sale/Purchase Summary": "HSN Wise Summary",
  "Form GSTR-3B2 Fill": "GSTR-3B Summary",
  "GSTR-2B Report Auto": "GST Register",
  "ITC Reversed & Claimed Report": "GST Register",
  "ITC Availed Report (Capital Goods & Services)": "GST Register",
  "Report GSTR-9": "GST Register",
  Backup: "Configuration",
  Users: "Office Users",
  "User Wise Company Setting": "Company Parameters",
  "Change Password": "Company Parameters",
  "Gst Rates Add": "Gst Rates Add",
  "Gst Rates Modify": "Gst Rates Modify",
  Settings: "Company Parameters",
  "Company Add": "Configuration",
  "Company Modify": "Configuration",
  "Company Delete": "Configuration",
  "Modify Parameters": "Company Parameters",
  "Prefix Setting": "Prefix Settings",
  "Account Merge": "Merge Parties",
  "City Merge": "Merge Parties",
  "A/c Group Merge": "Merge Parties",
  Calculator: "__calculator__",
  "Check & Correct": "System Diagnostics",
  "Missing Field Checking": "System Diagnostics",
  "Software Registration & Validation": "Configuration",
  "Auto System Checking": "System Diagnostics",
  Exit: "__exit__",
  "Stock Adjustment Add": "Stock Adjustment",
  "Stock Adjustment Modify": "Stock Adjustment",
};

export function resolveWindowTitle(title: string): ResolvedWindow {
  if (title.endsWith(" Add")) {
    const base = title.slice(0, -4);
    return { screen: SCREEN_ALIASES[base] ?? base, mode: "add" };
  }
  if (title.endsWith(" Modify")) {
    const base = title.slice(0, -7);
    return { screen: SCREEN_ALIASES[base] ?? base, mode: "modify" };
  }
  if (title === "Kachi Purchase Final") {
    return { screen: "Kachi Purchase Final" };
  }
  if (title === "Opening Bank Master") {
    return { screen: "Bank Master", mode: "add" };
  }
  if (title === "Closing Bank Master") {
    return { screen: "Bank Master", mode: "modify" };
  }
  return { screen: SCREEN_ALIASES[title] ?? title };
}

const MASTER_BASES = new Set([
  "Account Master",
  "Standard Narration Master",
  "City Master",
  "Transport Master",
  "Item Entry",
  "Stock Entry Master",
  "Bank Master",
  "IFSC Code Master",
  "Expenses Master Define",
  "Cheque Print Setting",
  "Trading Master",
  "I Form Expenses define",
]);

export function resolveMasterBase(title: string): string | null {
  const { screen } = resolveWindowTitle(title);
  if (MASTER_BASES.has(screen)) return screen;
  if (screen === "Account Master") return "Account Master";
  return null;
}

export function isMasterWindow(title: string): boolean {
  return resolveMasterBase(title) !== null;
}
