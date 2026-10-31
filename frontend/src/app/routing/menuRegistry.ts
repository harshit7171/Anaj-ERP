/** Reference-ERP style menus with hover flyouts (Add / Modify). */

export type MenuLeaf = { kind: "leaf"; label: string; window: string; disabled?: boolean };
export type MenuNode = { kind: "node"; label: string; children: MenuEntry[]; disabled?: boolean };
export type MenuEntry = MenuLeaf | MenuNode;

export type TopMenu = { id: string; label: string; items: MenuEntry[] };

function leaf(label: string, window?: string, disabled?: boolean): MenuLeaf {
  return { kind: "leaf", label, window: window ?? label, disabled };
}

function addModify(label: string, screen?: string): MenuNode {
  const base = screen ?? label;
  return {
    kind: "node",
    label,
    children: [
      leaf(`${label} Add`, `${base} Add`),
      leaf(`${label} Modify`, `${base} Modify`),
    ],
  };
}

export const masterMenu: TopMenu = {
  id: "master",
  label: "Master",
  items: [
    addModify("Account Master"),
    addModify("Standard Narration Master"),
    addModify("City Master"),
    addModify("Transport Master"),
    addModify("Trading Master"),
    leaf("Expenses Master Define"),
    leaf("I Form Expenses define", "I Form Expenses define"),
    addModify("Item Entry"),
    {
      kind: "node",
      label: "Stock Entry",
      children: [
        leaf("Opening Stock Entry", "Opening Stock Entry Add"),
        leaf("Closing Stock Entry", "Closing Stock Entry Modify"),
      ],
    },
    leaf("Cheque Print Setting"),
    addModify("Bank Master"),
    addModify("IFSC Code Master"),
  ],
};

export const dailyMenu: TopMenu = {
  id: "daily",
  label: "Daily",
  items: [
    addModify("Lifting Entry"),
    {
      kind: "node",
      label: "Kachi Purchase",
      children: [
        leaf("Kachi Purchase Add", "Kachi Purchase Add"),
        leaf("Kachi Purchase Modify", "Kachi Purchase Modify"),
        leaf("Kachi Purchase Final", "Kachi Purchase Final"),
      ],
    },
    addModify("Mandi Purchase Entry"),
    addModify("GST Purchase Entry"),
    addModify("Invoice"),
    addModify("J Form (Parchi)"),
    addModify("I Form (Auction Bill)"),
    addModify("I Form Lifting Entry"),
    leaf("Mandi Bhav Online"),
    leaf("Live Boli Board"),
    leaf("Live Boli Board (TV)", "Live Boli Board (TV)"),
    addModify("Debit Note"),
    addModify("Credit Note"),
    addModify("GST Debit Note"),
    addModify("GST Credit Note"),
    addModify("GST Expense Voucher"),
  ],
};

export const entryMenu: TopMenu = {
  id: "entry",
  label: "Entry",
  items: [
    addModify("Accounting Voucher"),
    addModify("Voucher Entry"),
    addModify("TDS Challan Entry"),
    addModify("Debit Note", "Debit Note"),
    addModify("Credit Note", "Credit Note"),
    { kind: "leaf", label: "Delivery Challan", window: "Delivery Challan", disabled: true },
    { kind: "node", label: "Consignment (Dr.)", disabled: true, children: [leaf("Consignment (Dr.) Add", "Consignment (Dr.)", true)] },
    { kind: "node", label: "Consignment (Cr.)", disabled: true, children: [leaf("Consignment (Cr.) Add", "Consignment (Cr.)", true)] },
    { kind: "leaf", label: "Milling", window: "Milling Inward", disabled: true },
    { kind: "leaf", label: "Inward/Outward", window: "Inward", disabled: true },
  ],
};

export const searchMenu: TopMenu = {
  id: "search",
  label: "Search",
  items: [
    leaf("Find Account"),
    leaf("Depreciation Chart"),
    addModify("Stock Adjustment"),
    leaf("Company Letter Head Print", "Company Letter Head Print"),
  ],
};

const accountingReports: MenuNode = {
  kind: "node",
  label: "Accounting Reports",
  children: [
    leaf("Cashbook"),
    leaf("Ledger"),
    leaf("Trial Balance"),
    leaf("Trading & I and Balance Sheet"),
    leaf("Account Balances Under a Group"),
    leaf("Cash in Hand Report"),
    leaf("Trial Balance Difference Report"),
    leaf("Combined Ledger"),
    leaf("Interest Statements"),
    leaf("Direct Interest"),
    leaf("Balancing Method Interest"),
    leaf("Mandi Dhara Interest"),
    leaf("Balancing Method Interest (Combined)"),
  ],
};

export const reportsMenu: TopMenu = {
  id: "reports",
  label: "Reports",
  items: [
    accountingReports,
    {
      kind: "node",
      label: "Reports 1",
      children: [
        leaf("Market Fees Report"),
        leaf("Due Date Report"),
        leaf("TDS Report"),
        leaf("Crop Sale Report(Kachi Aarat)"),
        leaf("JForm List"),
        leaf("Stock Register"),
        leaf("Stock Register (Kachi)"),
        leaf("Bill Wise Pending Balance"),
        leaf("Lifting Report"),
        leaf("Lifting Summary (Veh-Challan) Wise Report"),
        leaf("Bardana Report"),
        leaf("Bill Wise Purchase Detail"),
        leaf("Bill Wise Sale Detail"),
        leaf("Expense Wise Purchase Detail"),
        leaf("Debit Note Report"),
        leaf("Credit Note Report"),
        leaf("Bill Wise Sale Register"),
        leaf("Bill Wise Purchase Register"),
        leaf("Broker Commission Report"),
        leaf("Item-Wise Profitability"),
        leaf("Farmer Seasonal Turnover"),
        leaf("Buyer Payment Aging"),
        leaf("Mandi Cess M-Form Summary"),
        leaf("Daily Cash Drawer Reconciliation"),
      ],
    },
    {
      kind: "node",
      label: "Reports 2",
      children: [
        leaf("I-Form (From J-Form) List"),
        leaf("Talpat Report"),
        leaf("Kachi Purchase Report"),
      ],
    },
    {
      kind: "node",
      label: "GST Reports",
      children: [
        leaf("Purchase & Sale Summary"),
        leaf("Bill Wise Sale Detail(GST)"),
        leaf("Month Wise Item Wise Sale Report"),
        leaf("Month Wise Item Wise Purchase Report"),
        leaf("Gst Purchase Detail"),
        leaf("Form GSTR-1(Govt)"),
        leaf("GST Debit/Credit Note Report"),
        leaf("HSN Wise Sale/Purchase Summary"),
        leaf("Form GSTR-3B2 Fill"),
        leaf("GSTR-2B Report Auto"),
        leaf("ITC Reversed & Claimed Report"),
        leaf("ITC Availed Report (Capital Goods & Services)"),
        leaf("Report GSTR-9"),
        leaf("Clause 44 Tax Audit Export"),
      ],
    },
  ],
};

export const toolsMenu: TopMenu = {
  id: "tools",
  label: "Tools",
  items: [
    leaf("Backup", "Configuration"),
    leaf("Users", "Office Users"),
    leaf("User Wise Company Setting", "Company Parameters"),
    leaf("Change Password", "Company Parameters"),
    leaf("Gst Rates Add", "Gst Rates Add"),
    leaf("Gst Rates Modify", "Gst Rates Modify"),
    {
      kind: "node",
      label: "Settings",
      children: [
        leaf("Company Parameters"),
        leaf("User Alerts & WhatsApp", "User Alerts & WhatsApp"),
        leaf("Prefix Settings"),
        leaf("Cloud Backup", "Cloud Backup"),
        leaf("Google Drive Backup", "Cloud Backup"),
        leaf("Print Format Designer", "Print Format Designer"),
      ],
    },
    leaf("Company Add", "Configuration"),
    leaf("Company Modify", "Configuration"),
    leaf("Company Delete", "Configuration"),
    leaf("Modify Parameters", "Company Parameters"),
    leaf("Prefix Setting", "Prefix Settings"),
    {
      kind: "node",
      label: "Merging",
      children: [
        leaf("Account Merge", "Merge Parties"),
        leaf("City Merge", "Merge Parties"),
        leaf("A/c Group Merge", "Merge Parties"),
      ],
    },
    leaf("Closing", "Configuration"),
    leaf("Calculator", "__calculator__"),
    leaf("Check & Correct", "System Diagnostics"),
    leaf("Missing Field Checking", "System Diagnostics"),
    leaf("Software Registration & Validation", "Configuration"),
    leaf("Auto System Checking", "System Diagnostics"),
    leaf("Bank Reconciliation"),
    leaf("Reminder Letters"),
    leaf("Cover Printing"),
    leaf("Blended Cost Calculator"),
    leaf("System Diagnostics"),
    leaf("Exit", "__exit__"),
  ],
};

export const topMenus: TopMenu[] = [
  masterMenu,
  dailyMenu,
  entryMenu,
  searchMenu,
  reportsMenu,
  toolsMenu,
];
