export type VoucherLine = {
  account_id: string;
  account_name: string;
  balance: string;
  narration: string;
  amount: string;
  discount: string;
  due_date: string;
  cheque_no: string;
};

export function emptyVoucherLine(): VoucherLine {
  return {
    account_id: "",
    account_name: "",
    balance: "",
    narration: "",
    amount: "",
    discount: "",
    due_date: "",
    cheque_no: "",
  };
}

export function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

export function weekdayLabel(iso: string): string {
  if (!iso) return "";
  const day = new Date(`${iso}T12:00:00`).toLocaleDateString("en-IN", { weekday: "long" });
  return day;
}

export function withTrailingBlankLine(lines: VoucherLine[]): VoucherLine[] {
  const last = lines[lines.length - 1];
  if (last?.account_id || last?.amount) {
    return [...lines, emptyVoucherLine()];
  }
  return lines;
}

export function parseVoucherLines(raw: unknown): VoucherLine[] {
  if (!Array.isArray(raw) || raw.length === 0) return [emptyVoucherLine()];
  return raw.map((item) => {
    const row = item as Record<string, unknown>;
    const amount = row.amount ?? row.amount_paise;
    const discount = row.discount ?? row.discount_paise;
    let amountText = String(amount ?? "");
    if (/^\d+$/.test(amountText)) amountText = (Number(amountText) / 100).toFixed(2);
    let discountText = String(discount ?? "");
    if (/^\d+$/.test(discountText)) discountText = (Number(discountText) / 100).toFixed(2);
    return {
      account_id: String(row.account_id ?? ""),
      account_name: String(row.account_name ?? ""),
      balance: String(row.balance ?? ""),
      narration: String(row.narration ?? ""),
      amount: amountText,
      discount: discountText,
      due_date: String(row.due_date ?? ""),
      cheque_no: String(row.cheque_no ?? ""),
    };
  });
}
