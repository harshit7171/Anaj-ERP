import type { LiftingExpenseRow } from "../lifting-entry/constants";

export type GstLine = {
  commodity_id: string;
  item_name: string;
  item_desc: string;
  purchase_ac: string;
  purchase_ac_id: string;
  unit: string;
  sauda_no: string;
  qty: string;
  bharti: string;
  gross_wt: string;
  tare: string;
  adj_wt: string;
  net_wt: string;
  nw: string;
  rate: string;
  amount: string;
  hsn_code: string;
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

export function emptyGstLine(): GstLine {
  return {
    commodity_id: "",
    item_name: "",
    item_desc: "",
    purchase_ac: "",
    purchase_ac_id: "",
    unit: "Qtls",
    sauda_no: "",
    qty: "",
    bharti: "",
    gross_wt: "",
    tare: "",
    adj_wt: "",
    net_wt: "",
    nw: "N",
    rate: "",
    amount: "",
    hsn_code: "",
    gst_adj: "",
    cgst_pct: "2.5",
    sgst_pct: "2.5",
    igst_pct: "0",
    gst_amt: "0.00",
  };
}

export function withTrailingBlankLine(lines: GstLine[]): GstLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.item_name.trim()) copy.push(emptyGstLine());
  else if (!copy.length) copy.push(emptyGstLine());
  return copy;
}

export function parseGstLines(raw: unknown): GstLine[] {
  if (!Array.isArray(raw) || !raw.length) return [emptyGstLine()];
  return withTrailingBlankLine(
    raw.map((row) => {
      const item = row as Record<string, unknown>;
      return {
        commodity_id: String(item.commodity_id ?? ""),
        item_name: String(item.item_name ?? ""),
        item_desc: String(item.item_desc ?? item.item_name ?? ""),
        purchase_ac: String(item.purchase_ac ?? ""),
        purchase_ac_id: String(item.purchase_ac_id ?? ""),
        unit: String(item.unit ?? "Qtls"),
        sauda_no: String(item.sauda_no ?? ""),
        qty: String(item.qty ?? ""),
        bharti: String(item.bharti ?? ""),
        gross_wt: String(item.gross_wt ?? ""),
        tare: String(item.tare ?? ""),
        adj_wt: String(item.adj_wt ?? ""),
        net_wt: String(item.net_wt ?? ""),
        nw: String(item.nw ?? "N"),
        rate: String(item.rate ?? ""),
        amount: String(item.amount ?? ""),
        hsn_code: String(item.hsn_code ?? ""),
        gst_adj: String(item.gst_adj ?? ""),
        cgst_pct: String(item.cgst_pct ?? "2.5"),
        sgst_pct: String(item.sgst_pct ?? "2.5"),
        igst_pct: String(item.igst_pct ?? "0"),
        gst_amt: String(item.gst_amt ?? "0.00"),
      };
    }),
  );
}

export function recalcGstLine(line: GstLine): GstLine {
  const gross = Number(line.gross_wt) || 0;
  const tare = Number(line.tare) || 0;
  const adj = Number(line.adj_wt) || 0;
  const qty = Number(line.qty) || 0;
  let net = Number(line.net_wt);
  if (!Number.isFinite(net) || net <= 0) {
    net = Math.max(0, gross - tare + adj);
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

export function buildRateSummary(lines: GstLine[]): RateSummaryRow[] {
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

export function sumGstHeaderTotals(lines: GstLine[]) {
  let taxable = 0;
  let gst = 0;
  for (const line of lines) {
    if (!line.item_name.trim()) continue;
    taxable += Number(line.amount) || 0;
    gst += Number(line.gst_amt) || 0;
  }
  const bill = taxable + gst;
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
