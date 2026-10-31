import type { LiftingExpenseRow } from "../lifting-entry/constants";

export type MandiLine = {
  line_party_id: string;
  party_name: string;
  bill_no: string;
  due_date: string;
  commodity_id: string;
  item_name: string;
  unit: string;
  nugs: string;
  weight: string;
  nw: string;
  rate: string;
  amount: string;
  r_off: string;
  bill_amt: string;
  tds_on: string;
  tds_pct: string;
  tds_on_amt: string;
  tds: string;
  ref_code: string;
};

export type ItemSummaryRow = {
  item_name: string;
  nugs: string;
  weight: string;
  amount: string;
  avg_rate: string;
};

export type TransportTab = {
  transporter: string;
  vehicle_no: string;
  freight: string;
  remarks: string;
};

export type BardanaTab = {
  bardana_type: string;
  bags: string;
  remarks: string;
};

export function emptyMandiLine(): MandiLine {
  return {
    line_party_id: "",
    party_name: "",
    bill_no: "",
    due_date: "",
    commodity_id: "",
    item_name: "",
    unit: "Qtls",
    nugs: "",
    weight: "",
    nw: "N",
    rate: "",
    amount: "",
    r_off: "Y",
    bill_amt: "",
    tds_on: "N",
    tds_pct: "",
    tds_on_amt: "",
    tds: "0.00",
    ref_code: "PU1",
  };
}

export function withTrailingBlankLine(lines: MandiLine[]): MandiLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.party_name.trim() || last?.item_name.trim()) {
    copy.push(emptyMandiLine());
  } else if (!copy.length) {
    copy.push(emptyMandiLine());
  }
  return copy;
}

export function parseMandiLines(raw: unknown): MandiLine[] {
  if (!Array.isArray(raw) || !raw.length) return [emptyMandiLine()];
  return withTrailingBlankLine(
    raw.map((row) => {
      const item = row as Record<string, unknown>;
      return {
        line_party_id: String(item.line_party_id ?? ""),
        party_name: String(item.party_name ?? ""),
        bill_no: String(item.bill_no ?? ""),
        due_date: String(item.due_date ?? ""),
        commodity_id: String(item.commodity_id ?? ""),
        item_name: String(item.item_name ?? ""),
        unit: String(item.unit ?? "Qtls"),
        nugs: String(item.nugs ?? ""),
        weight: String(item.weight ?? ""),
        nw: String(item.nw ?? "N"),
        rate: String(item.rate ?? ""),
        amount: String(item.amount ?? ""),
        r_off: String(item.r_off ?? "Y"),
        bill_amt: String(item.bill_amt ?? ""),
        tds_on: String(item.tds_on ?? "N"),
        tds_pct: String(item.tds_pct ?? ""),
        tds_on_amt: String(item.tds_on_amt ?? ""),
        tds: String(item.tds ?? "0.00"),
        ref_code: String(item.ref_code ?? "PU1"),
      };
    }),
  );
}

export function recalcMandiLine(line: MandiLine, headerTdsRate: string): MandiLine {
  const weight = Number(line.weight);
  const rate = Number(line.rate);
  if (!Number.isFinite(weight) || !Number.isFinite(rate)) {
    return { ...line, amount: line.amount || "0.00" };
  }
  const roundOff = line.r_off.toUpperCase().startsWith("Y");
  let amount = weight * rate;
  if (roundOff) amount = Math.round(amount);
  const amountStr = amount.toFixed(2);
  const tdsOn = line.tds_on.toUpperCase().startsWith("Y");
  const pct = Number(line.tds_pct || headerTdsRate) || 0;
  const tdsBase = tdsOn ? amount : 0;
  const tds = ((tdsBase * pct) / 100).toFixed(2);
  return {
    ...line,
    amount: amountStr,
    bill_amt: amountStr,
    tds_on_amt: tdsOn ? amountStr : "0.00",
    tds,
  };
}

export function buildItemSummary(lines: MandiLine[]): ItemSummaryRow[] {
  const map = new Map<string, { nugs: number; weight: number; amount: number }>();
  for (const line of lines) {
    if (!line.item_name.trim()) continue;
    const key = line.item_name.trim();
    const bucket = map.get(key) ?? { nugs: 0, weight: 0, amount: 0 };
    bucket.nugs += Number(line.nugs) || 0;
    bucket.weight += Number(line.weight) || 0;
    bucket.amount += Number(line.bill_amt || line.amount) || 0;
    map.set(key, bucket);
  }
  return [...map.entries()].map(([item_name, bucket]) => ({
    item_name,
    nugs: bucket.nugs.toFixed(2),
    weight: bucket.weight.toFixed(3),
    amount: bucket.amount.toFixed(2),
    avg_rate: bucket.weight > 0 ? (bucket.amount / bucket.weight).toFixed(2) : "0.00",
  }));
}

export function sumMandiTotals(lines: MandiLine[]) {
  let nugs = 0;
  let weight = 0;
  let amount = 0;
  let tds = 0;
  for (const line of lines) {
    if (!line.item_name.trim() && !line.party_name.trim()) continue;
    nugs += Number(line.nugs) || 0;
    weight += Number(line.weight) || 0;
    amount += Number(line.bill_amt || line.amount) || 0;
    tds += Number(line.tds) || 0;
  }
  return {
    total_nugs: nugs.toFixed(2),
    total_weight: weight.toFixed(3),
    total_amount: amount.toFixed(2),
    total_tds: tds.toFixed(2),
  };
}

export function weekdayLabel(isoOrDdMm: string): string {
  const iso = isoOrDdMm.includes("/") ? ddMmYyyyToIso(isoOrDdMm) : isoOrDdMm;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "";
  const date = new Date(`${iso}T12:00:00`);
  return date.toLocaleDateString("en-IN", { weekday: "long" });
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

export type { LiftingExpenseRow };
