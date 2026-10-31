export type LiftingExpenseRow = {
  particulars: string;
  exp_on: string;
  extra: string;
  per_pct: string;
  r_off: string;
  amount: string;
};

export type LiftingLine = {
  commodity_id: string;
  line_party_id: string;
  party_name: string;
  remarks: string;
  item_name: string;
  unit: string;
  rate: string;
  ref_code: string;
  reference: string;
  qty: string;
  weight: string;
  amount: string;
};

export type LiftedSummaryRow = {
  item_name: string;
  lifted_qty: string;
};

export function emptyLiftingLine(): LiftingLine {
  return {
    commodity_id: "",
    line_party_id: "",
    party_name: "",
    remarks: "",
    item_name: "",
    unit: "Qtls",
    rate: "",
    ref_code: "",
    reference: "",
    qty: "",
    weight: "",
    amount: "",
  };
}

export function emptyExpenseRow(): LiftingExpenseRow {
  return {
    particulars: "",
    exp_on: "Nug",
    extra: "N",
    per_pct: "",
    r_off: "N",
    amount: "",
  };
}

export function withTrailingBlankLine(lines: LiftingLine[]): LiftingLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.party_name.trim() || last?.item_name.trim()) {
    copy.push(emptyLiftingLine());
  } else if (!copy.length) {
    copy.push(emptyLiftingLine());
  }
  return copy;
}

export function parseLiftingLines(raw: unknown): LiftingLine[] {
  if (!Array.isArray(raw) || !raw.length) return [emptyLiftingLine()];
  return withTrailingBlankLine(
    raw.map((row) => {
      const item = row as Record<string, unknown>;
      return {
        commodity_id: String(item.commodity_id ?? ""),
        line_party_id: String(item.line_party_id ?? ""),
        party_name: String(item.party_name ?? ""),
        remarks: String(item.remarks ?? ""),
        item_name: String(item.item_name ?? ""),
        unit: String(item.unit ?? "Qtls"),
        rate: String(item.rate ?? ""),
        ref_code: String(item.ref_code ?? ""),
        reference: String(item.reference ?? ""),
        qty: String(item.qty ?? ""),
        weight: String(item.weight ?? ""),
        amount: String(item.amount ?? ""),
      };
    }),
  );
}

export function recalcLineAmount(line: LiftingLine): LiftingLine {
  const weight = Number(line.weight);
  const rate = Number(line.rate);
  if (!Number.isFinite(weight) || !Number.isFinite(rate)) {
    return { ...line, amount: line.amount || "0.00" };
  }
  const amount = (weight * rate).toFixed(2);
  return { ...line, amount };
}

export function sumTotals(lines: LiftingLine[], expenseTotal: number) {
  let totalQty = 0;
  let totalWeight = 0;
  let totalAmount = 0;
  for (const line of lines) {
    if (!line.item_name.trim() && !line.party_name.trim()) continue;
    totalQty += Number(line.qty) || 0;
    totalWeight += Number(line.weight) || 0;
    totalAmount += Number(line.amount) || 0;
  }
  const totalExpense = expenseTotal;
  return {
    total_qty: totalQty.toFixed(2),
    total_weight: totalWeight.toFixed(3),
    total_amount: totalAmount.toFixed(2),
    total_expense: totalExpense.toFixed(2),
    total_amt_exp: (totalAmount + totalExpense).toFixed(2),
  };
}

export function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

export function ddMmYyyyToIso(value: string): string {
  const trimmed = value.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(trimmed);
  if (!match) return trimmed;
  const [, d, m, y] = match;
  return `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
}

export function isoToDdMmYyyy(iso: string): string {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return iso;
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}
