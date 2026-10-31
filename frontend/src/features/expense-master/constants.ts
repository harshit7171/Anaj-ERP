export const EXPENSE_NATURES = ["Dami", "Unit", "Market", "RDF"] as const;
export const EXPENSES_ON = ["Amt", "Nugs"] as const;
export const EXPENSE_DR_CR = ["D", "C"] as const;
export const EXPENSE_R_OFF = ["N", "Y"] as const;

export type ExpenseLine = {
  expense_name: string;
  nature: (typeof EXPENSE_NATURES)[number];
  expenses_on: (typeof EXPENSES_ON)[number];
  rate: string;
  stage: string;
  account_name: string;
  dr_cr: (typeof EXPENSE_DR_CR)[number];
  r_off: (typeof EXPENSE_R_OFF)[number];
  rcm_applicable: string;
  blocked_itc: string;
};

export function emptyExpenseLine(): ExpenseLine {
  return {
    expense_name: "",
    nature: "Dami",
    expenses_on: "Amt",
    rate: "0",
    stage: "1",
    account_name: "",
    dr_cr: "D",
    r_off: "N",
    rcm_applicable: "No",
    blocked_itc: "No",
  };
}
