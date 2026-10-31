import type { LiftingExpenseRow } from "../lifting-entry/constants";

export type InvoiceLine = {
  commodity_id: string;
  item_name: string;
  item_desc: string;
  sale_ac: string;
  sale_ac_id: string;
  unit: string;
  qty: string;
  bharti: string;
  gross_wt: string;
  tare: string;
  shortage: string;
  net_wt: string;
  nw: string;
  rate: string;
  amount: string;
  diff: string;
  gst_adj: string;
  cgst_pct: string;
  sgst_pct: string;
  igst_pct: string;
  gst_amt: string;
};

export type RateSummaryRow = {
  rate: string;
  gst_on: string;
  cgst: string;
  sgst: string;
  igst: string;
  total_gst: string;
  total: string;
};

export type SideCategoryRow = {
  item_name: string;
  nugs: string;
  weight: string;
  amount: string;
};

export function emptySideRow(): SideCategoryRow {
  return { item_name: "", nugs: "", weight: "", amount: "" };
}

export function emptyInvoiceLine(): InvoiceLine {
  return {
    commodity_id: "",
    item_name: "",
    item_desc: "",
    sale_ac: "",
    sale_ac_id: "",
    unit: "Qtls",
    qty: "",
    bharti: "",
    gross_wt: "",
    tare: "",
    shortage: "",
    net_wt: "",
    nw: "N",
    rate: "",
    amount: "",
    diff: "",
    gst_adj: "",
    cgst_pct: "2.5",
    sgst_pct: "2.5",
    igst_pct: "0",
    gst_amt: "0.00",
  };
}

export function withTrailingBlankLine(lines: InvoiceLine[]): InvoiceLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.item_name.trim()) copy.push(emptyInvoiceLine());
  else if (!copy.length) copy.push(emptyInvoiceLine());
  return copy;
}

export function parseInvoiceLines(raw: unknown): InvoiceLine[] {
  if (!Array.isArray(raw) || !raw.length) return [emptyInvoiceLine()];
  return withTrailingBlankLine(
    raw.map((row) => {
      const item = row as Record<string, unknown>;
      return {
        commodity_id: String(item.commodity_id ?? ""),
        item_name: String(item.item_name ?? ""),
        item_desc: String(item.item_desc ?? item.item_name ?? ""),
        sale_ac: String(item.sale_ac ?? ""),
        sale_ac_id: String(item.sale_ac_id ?? ""),
        unit: String(item.unit ?? "Qtls"),
        qty: String(item.qty ?? ""),
        bharti: String(item.bharti ?? ""),
        gross_wt: String(item.gross_wt ?? ""),
        tare: String(item.tare ?? ""),
        shortage: String(item.shortage ?? ""),
        net_wt: String(item.net_wt ?? ""),
        nw: String(item.nw ?? "N"),
        rate: String(item.rate ?? ""),
        amount: String(item.amount ?? ""),
        diff: String(item.diff ?? ""),
        gst_adj: String(item.gst_adj ?? ""),
        cgst_pct: String(item.cgst_pct ?? "2.5"),
        sgst_pct: String(item.sgst_pct ?? "2.5"),
        igst_pct: String(item.igst_pct ?? "0"),
        gst_amt: String(item.gst_amt ?? "0.00"),
      };
    }),
  );
}

export function recalcInvoiceLine(line: InvoiceLine): InvoiceLine {
  const gross = Number(line.gross_wt) || 0;
  const tare = Number(line.tare) || 0;
  const shortage = Number(line.shortage) || 0;
  const qty = Number(line.qty) || 0;
  let net = Number(line.net_wt);
  if (!Number.isFinite(net) || net <= 0) {
    net = Math.max(0, gross - tare - shortage);
  }
  const rate = Number(line.rate) || 0;
  const taxable = net > 0 ? net * rate : qty * rate;
  const amount = taxable.toFixed(2);
  const cgst = Number(line.cgst_pct) || 0;
  const sgst = Number(line.sgst_pct) || 0;
  const igst = Number(line.igst_pct) || 0;
  const gstAmt = ((taxable * (cgst + sgst + igst)) / 100).toFixed(2);
  return {
    ...line,
    net_wt: net > 0 ? net.toFixed(3) : line.net_wt,
    amount,
    gst_amt: gstAmt,
  };
}

export function buildRateSummary(lines: InvoiceLine[]): RateSummaryRow[] {
  const map = new Map<string, RateSummaryRow>();
  for (const line of lines) {
    if (!line.item_name.trim()) continue;
    const key = `${line.rate}|${line.cgst_pct}|${line.sgst_pct}|${line.igst_pct}`;
    const taxable = Number(line.amount) || 0;
    const cgstAmt = (taxable * (Number(line.cgst_pct) || 0)) / 100;
    const sgstAmt = (taxable * (Number(line.sgst_pct) || 0)) / 100;
    const igstAmt = (taxable * (Number(line.igst_pct) || 0)) / 100;
    const gstTotal = cgstAmt + sgstAmt + igstAmt;
    const bucket = map.get(key) ?? {
      rate: line.rate,
      gst_on: "0.00",
      cgst: "0.00",
      sgst: "0.00",
      igst: "0.00",
      total_gst: "0.00",
      total: "0.00",
    };
    bucket.gst_on = (Number(bucket.gst_on) + taxable).toFixed(2);
    bucket.cgst = (Number(bucket.cgst) + cgstAmt).toFixed(2);
    bucket.sgst = (Number(bucket.sgst) + sgstAmt).toFixed(2);
    bucket.igst = (Number(bucket.igst) + igstAmt).toFixed(2);
    bucket.total_gst = (Number(bucket.total_gst) + gstTotal).toFixed(2);
    bucket.total = (Number(bucket.gst_on) + Number(bucket.total_gst)).toFixed(2);
    map.set(key, bucket);
  }
  return [...map.values()];
}

export function buildLineSideRows(lines: InvoiceLine[]): SideCategoryRow[] {
  return lines
    .filter((line) => line.item_name.trim())
    .map((line) => ({
      item_name: line.item_name,
      nugs: line.qty,
      weight: line.net_wt,
      amount: line.amount,
    }));
}

export function sumInvoiceHeaderTotals(lines: InvoiceLine[], rOffAmt: string) {
  let taxable = 0;
  let gst = 0;
  for (const line of lines) {
    if (!line.item_name.trim()) continue;
    taxable += Number(line.amount) || 0;
    gst += Number(line.gst_amt) || 0;
  }
  const roff = Number(rOffAmt) || 0;
  const bill = taxable + gst + roff;
  return {
    gst_amt: gst.toFixed(2),
    bill_amt: bill.toFixed(2),
    taxable: taxable.toFixed(2),
  };
}

export function weekdayLabel(isoOrDdMm: string): string {
  const iso = isoOrDdMm.includes("/") ? ddMmYyyyToIso(isoOrDdMm) : isoOrDdMm;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "";
  return new Date(`${iso}T12:00:00`).toLocaleDateString("en-IN", { weekday: "long" });
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
