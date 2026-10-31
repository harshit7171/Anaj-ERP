export type StockEntryKind = "opening" | "closing";

export type StockLine = {
  line_id: string;
  commodity_id: string;
  item_name: string;
  unit: string;
  account_id: string;
  account_name: string;
  qty: string;
  weight: string;
  rate: string;
  amount: string;
  mm: string;
};

export function emptyStockLine(): StockLine {
  return {
    line_id: "",
    commodity_id: "",
    item_name: "",
    unit: "",
    account_id: "",
    account_name: "",
    qty: "",
    weight: "",
    rate: "",
    amount: "",
    mm: "",
  };
}

export function parseStockLines(raw: unknown): StockLine[] {
  if (!Array.isArray(raw) || !raw.length) {
    return [emptyStockLine()];
  }
  return raw.map((row) => {
    const item = row as Record<string, unknown>;
    return {
      line_id: String(item.line_id ?? ""),
      commodity_id: String(item.commodity_id ?? ""),
      item_name: String(item.item_name ?? ""),
      unit: String(item.unit ?? ""),
      account_id: String(item.account_id ?? ""),
      account_name: String(item.account_name ?? ""),
      qty: String(item.qty ?? ""),
      weight: String(item.weight ?? ""),
      rate: String(item.rate ?? ""),
      amount: String(item.amount ?? ""),
      mm: String(item.mm ?? ""),
    };
  });
}

export function withTrailingBlankLine(lines: StockLine[]): StockLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.item_name.trim()) {
    copy.push(emptyStockLine());
  } else if (!copy.length) {
    copy.push(emptyStockLine());
  }
  return copy;
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
