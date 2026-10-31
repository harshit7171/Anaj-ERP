export type KachiLine = {
  seller_party_id: string;
  seller_name: string;
  slip_no: string;
  bill_no: string;
  bill_date: string;
  commodity_id: string;
  item_name: string;
  bharti: string;
  bags: string;
  weight: string;
  rate: string;
  amount: string;
};

export function emptyKachiLine(slipNo = ""): KachiLine {
  return {
    seller_party_id: "",
    seller_name: "",
    slip_no: slipNo,
    bill_no: "",
    bill_date: "",
    commodity_id: "",
    item_name: "",
    bharti: "",
    bags: "",
    weight: "",
    rate: "",
    amount: "",
  };
}

export function withTrailingBlankLine(lines: KachiLine[]): KachiLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.seller_name.trim() || last?.item_name.trim()) {
    copy.push(emptyKachiLine(String(copy.length + 1)));
  } else if (!copy.length) {
    copy.push(emptyKachiLine("1"));
  }
  return copy;
}

export function parseKachiLines(raw: unknown): KachiLine[] {
  if (!Array.isArray(raw) || !raw.length) return [emptyKachiLine("1")];
  return withTrailingBlankLine(
    raw.map((row, index) => {
      const item = row as Record<string, unknown>;
      return {
        seller_party_id: String(item.seller_party_id ?? ""),
        seller_name: String(item.seller_name ?? ""),
        slip_no: String(item.slip_no ?? index + 1),
        bill_no: String(item.bill_no ?? ""),
        bill_date: String(item.bill_date ?? ""),
        commodity_id: String(item.commodity_id ?? ""),
        item_name: String(item.item_name ?? ""),
        bharti: String(item.bharti ?? ""),
        bags: String(item.bags ?? ""),
        weight: String(item.weight ?? ""),
        rate: String(item.rate ?? ""),
        amount: String(item.amount ?? ""),
      };
    }),
  );
}

export function recalcLine(line: KachiLine): KachiLine {
  const weight = Number(line.weight);
  const rate = Number(line.rate);
  if (!Number.isFinite(weight) || !Number.isFinite(rate)) {
    return { ...line, amount: line.amount || "0.00" };
  }
  return { ...line, amount: (weight * rate).toFixed(2) };
}

export function sumKachiTotals(lines: KachiLine[]) {
  let bags = 0;
  let weight = 0;
  let amount = 0;
  for (const line of lines) {
    if (!line.item_name.trim() && !line.seller_name.trim()) continue;
    bags += Number(line.bags) || 0;
    weight += Number(line.weight) || 0;
    amount += Number(line.amount) || 0;
  }
  const avgRate = weight > 0 ? amount / weight : 0;
  return {
    total_bags: bags.toFixed(2),
    total_weight: weight.toFixed(3),
    avg_rate: avgRate.toFixed(2),
    total_amount: amount.toFixed(2),
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
