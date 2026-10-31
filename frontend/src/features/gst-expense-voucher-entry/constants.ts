export type GstDebitLine = {
  line_account_id: string;
  line_account_name: string;
  commodity_id: string;
  item_name: string;
  item_desc: string;
  bags: string;
  qty: string;
  rate: string;
  disc_pct: string;
  disc_amt: string;
  amount: string;
  hsn_code: string;
  gst_diff: string;
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

export function emptyDebitLine(): GstDebitLine {
  return {
    line_account_id: "",
    line_account_name: "",
    commodity_id: "",
    item_name: "",
    item_desc: "",
    bags: "",
    qty: "",
    rate: "",
    disc_pct: "",
    disc_amt: "",
    amount: "",
    hsn_code: "",
    gst_diff: "",
    cgst_pct: "2.5",
    sgst_pct: "2.5",
    igst_pct: "0",
    gst_amt: "0.00",
  };
}

export function withTrailingBlankLine(lines: GstDebitLine[]): GstDebitLine[] {
  const copy = [...lines];
  const last = copy[copy.length - 1];
  if (last?.item_name.trim()) copy.push(emptyDebitLine());
  else if (!copy.length) copy.push(emptyDebitLine());
  return copy;
}

export function parseDebitLines(raw: unknown): GstDebitLine[] {
  if (!Array.isArray(raw) || !raw.length) return [emptyDebitLine()];
  return withTrailingBlankLine(
    raw.map((row) => {
      const item = row as Record<string, unknown>;
      return {
        line_account_id: String(item.line_account_id ?? ""),
        line_account_name: String(item.line_account_name ?? item.line_ac ?? ""),
        commodity_id: String(item.commodity_id ?? ""),
        item_name: String(item.item_name ?? ""),
        item_desc: String(item.item_desc ?? item.item_name ?? ""),
        bags: String(item.bags ?? ""),
        qty: String(item.qty ?? ""),
        rate: String(item.rate ?? ""),
        disc_pct: String(item.disc_pct ?? ""),
        disc_amt: String(item.disc_amt ?? ""),
        amount: String(item.amount ?? ""),
        hsn_code: String(item.hsn_code ?? ""),
        gst_diff: String(item.gst_diff ?? ""),
        cgst_pct: String(item.cgst_pct ?? "2.5"),
        sgst_pct: String(item.sgst_pct ?? "2.5"),
        igst_pct: String(item.igst_pct ?? "0"),
        gst_amt: String(item.gst_amt ?? "0.00"),
      };
    }),
  );
}

export function recalcDebitLine(line: GstDebitLine): GstDebitLine {
  const qty = Number(line.qty) || Number(line.bags) || 0;
  const rate = Number(line.rate) || 0;
  const discPct = Number(line.disc_pct) || 0;
  let discAmt = Number(line.disc_amt);
  if (!Number.isFinite(discAmt) || (discAmt === 0 && discPct > 0)) {
    discAmt = (qty * rate * discPct) / 100;
  }
  const taxable = Math.max(0, qty * rate - discAmt);
  const amount = taxable.toFixed(2);
  const cgst = Number(line.cgst_pct) || 0;
  const sgst = Number(line.sgst_pct) || 0;
  const igst = Number(line.igst_pct) || 0;
  const gstAmt = ((taxable * (cgst + sgst + igst)) / 100).toFixed(2);
  return {
    ...line,
    qty: qty > 0 ? String(qty) : line.qty,
    disc_amt: discAmt > 0 ? discAmt.toFixed(2) : line.disc_amt,
    amount,
    gst_amt: gstAmt,
  };
}

export function buildRateSummary(lines: GstDebitLine[]): RateSummaryRow[] {
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

export function sumDebitHeaderTotals(lines: GstDebitLine[], rOffAmt: string) {
  let taxable = 0;
  let gst = 0;
  for (const line of lines) {
    if (!line.item_name.trim()) continue;
    taxable += Number(line.amount) || 0;
    gst += Number(line.gst_amt) || 0;
  }
  const roff = Number(rOffAmt) || 0;
  return {
    gst_amt: gst.toFixed(2),
    bill_amt: (taxable + gst + roff).toFixed(2),
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
