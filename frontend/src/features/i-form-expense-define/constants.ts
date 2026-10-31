export const I_FORM_EXPENSE_NAMES = [
  "J Form Exp - 1",
  "J Form Exp - 2",
  "I Form Labour",
  "I Form Loading",
  "I Form Stiching",
  "I Form Gaushala",
  "I Form - 5",
  "I Form - 6",
  "I Form - 7",
  "Labour Division Exp - 1",
  "Labour Division Exp - 2",
  "Labour Division Exp - 3",
  "Labour Division Exp - 4",
  "Labour Division Exp - 5",
] as const;

export const I_FORM_RATE_ON = ["A", "Amt", "Nugs"] as const;
export const I_FORM_R_OFF = ["N", "Y"] as const;

export type IFormExpenseLine = {
  expense_name: string;
  display_name: string;
  rate: string;
  rate_on: (typeof I_FORM_RATE_ON)[number];
  account_name: string;
  round_off: (typeof I_FORM_R_OFF)[number];
};

/** Blank grid on first open — names only; rates filled after Show (F5). */
export function blankIFormLines(): IFormExpenseLine[] {
  return I_FORM_EXPENSE_NAMES.map((name) => ({
    expense_name: name,
    display_name: "",
    rate: "",
    rate_on: "A",
    account_name: "",
    round_off: "N",
  }));
}

export function defaultIFormLines(): IFormExpenseLine[] {
  return blankIFormLines();
}
