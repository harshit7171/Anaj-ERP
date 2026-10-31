/**
 * Single index of menu windows → feature module paths (for humans and Cursor).
 * Router implementation: `features/legacy/EntryWindowImpl.tsx` (being split by domain).
 */

export type WindowCatalogEntry = {
  /** Menu / modal title as opened from the shell */
  windowTitle: string;
  /** Resolved screen id from windowRouting */
  screen: string;
  /** Feature folder or primary file */
  modulePath: string;
  backend?: string;
  notes?: string;
};

export const windowCatalog: WindowCatalogEntry[] = [
  {
    windowTitle: "Account Master Add",
    screen: "Account Master",
    modulePath: "frontend/src/features/account-master/",
    backend: "backend/anaj_erp/masters.py (save_account_master, …)",
    notes: "Ctrl+A shortcut; F3/F4/F5 on screen",
  },
  {
    windowTitle: "Account Master Modify",
    screen: "Account Master",
    modulePath: "frontend/src/features/account-master/",
    backend: "backend/anaj_erp/masters.py",
  },
  {
    windowTitle: "City Master Add",
    screen: "City Master",
    modulePath: "frontend/src/features/city-master/",
    backend: "backend/anaj_erp/masters.py (list/get/save/delete_city)",
  },
  {
    windowTitle: "Master Transport Add",
    screen: "Transport Master",
    modulePath: "frontend/src/features/transport-master/",
    backend: "backend/anaj_erp/masters.py (list/get/save/delete_transport)",
  },
  {
    windowTitle: "Trading Account Add",
    screen: "Trading Master",
    modulePath: "frontend/src/features/trading-account/",
    backend: "backend/anaj_erp/masters.py (trading_account + list_items)",
    notes: "Menu label Trading Master Add/Modify",
  },
  {
    windowTitle: "Expenses Master Define",
    screen: "Expenses Master Define",
    modulePath: "frontend/src/features/expense-master/",
    backend: "backend/anaj_erp/masters.py (expense_master lines_json)",
  },
  {
    windowTitle: "Define I Form Expense",
    screen: "I Form Expenses define",
    modulePath: "frontend/src/features/i-form-expense-define/",
    backend: "backend/anaj_erp/masters.py (i_form_expense_define)",
  },
  {
    windowTitle: "Master Item Add",
    screen: "Item Entry",
    modulePath: "frontend/src/features/item-entry/",
    backend: "backend/anaj_erp/masters.py (list/get/save/delete_item)",
    notes: "Menu Item Entry Add/Modify",
  },
  {
    windowTitle: "Master Item Modify",
    screen: "Item Entry",
    modulePath: "frontend/src/features/item-entry/",
    backend: "backend/anaj_erp/masters.py",
  },
  {
    windowTitle: "Cheque Printing Setting",
    screen: "Cheque Print Setting",
    modulePath: "frontend/src/features/cheque-print-setting/",
    backend: "backend/anaj_erp/masters.py (list/get/save/delete_cheque_print_setting)",
    notes: "Menu: Cheque Print Setting; dimensions in centimeters",
  },
  {
    windowTitle: "Bank Master Add",
    screen: "Bank Master",
    modulePath: "frontend/src/features/bank-master/",
    backend: "backend/anaj_erp/masters.py (list/get/save/delete_bank)",
    notes: "Legacy menu Opening Bank Master also opens Add",
  },
  {
    windowTitle: "Bank Master Modify",
    screen: "Bank Master",
    modulePath: "frontend/src/features/bank-master/",
    backend: "backend/anaj_erp/masters.py",
    notes: "Legacy menu Closing Bank Master also opens Modify",
  },
  {
    windowTitle: "IFSC Master Add",
    screen: "IFSC Code Master",
    modulePath: "frontend/src/features/ifsc-master/",
    backend: "backend/anaj_erp/masters.py (list/get/save/delete_ifsc)",
  },
  {
    windowTitle: "IFSC Master Modify",
    screen: "IFSC Code Master",
    modulePath: "frontend/src/features/ifsc-master/",
    backend: "backend/anaj_erp/masters.py",
  },
  {
    windowTitle: "Opening Stock Entry",
    screen: "Stock Entry Master",
    modulePath: "frontend/src/features/stock-entry-master/",
    backend: "backend/anaj_erp/masters.py (stock_entry_master + opening_stock)",
    notes: "Menu: Opening Stock Entry",
  },
  {
    windowTitle: "Closing Stock Entry",
    screen: "Stock Entry Master",
    modulePath: "frontend/src/features/stock-entry-master/",
    backend: "backend/anaj_erp/masters.py",
    notes: "Menu: Closing Stock Entry",
  },
  {
    windowTitle: "Cash Book",
    screen: "Cash Book",
    modulePath: "frontend/src/features/legacy/EntryWindowImpl.tsx (CashBookForm)",
    backend: "backend/anaj_erp/accounting.py",
  },
  {
    windowTitle: "Journal",
    screen: "Journal",
    modulePath: "frontend/src/features/legacy/EntryWindowImpl.tsx (JournalForm)",
    backend: "backend/anaj_erp/accounting.py (post_voucher)",
  },
  {
    windowTitle: "Kachi Purchase Add",
    screen: "Kachi Purchase",
    modulePath: "frontend/src/DenseDocumentForm.tsx",
    backend: "backend/anaj_erp/documents.py, mandi_bills.py",
  },
  {
    windowTitle: "Sale Invoice",
    screen: "Sale Invoice",
    modulePath: "frontend/src/features/legacy/EntryWindowImpl.tsx (SaleBill)",
    backend: "backend/anaj_erp/documents.py",
  },
  {
    windowTitle: "Find Account",
    screen: "Find Account",
    modulePath: "frontend/src/screens/ToolsScreens.tsx",
    backend: "backend/anaj_erp/tools.py (find_accounts)",
  },
  {
    windowTitle: "Gst Rates Add",
    screen: "Gst Rates",
    modulePath: "frontend/src/screens/GstRatesScreen.tsx",
    backend: "backend/anaj_erp/tools.py (company settings)",
  },
];

/** Lookup helper for agents — pass exact menu title or screen id. */
export function findWindowCatalog(query: string): WindowCatalogEntry[] {
  const q = query.trim().toLowerCase();
  return windowCatalog.filter(
    (row) =>
      row.windowTitle.toLowerCase().includes(q)
      || row.screen.toLowerCase().includes(q)
      || row.modulePath.toLowerCase().includes(q),
  );
}
