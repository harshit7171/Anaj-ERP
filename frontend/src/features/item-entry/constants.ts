export const YES_NO = ["Yes", "No"] as const;
export const RATE_PER_UNITS = ["Bags", "Qtls", "Kg", "MT"] as const;
export const ITEM_TYPES = ["Item", "Service"] as const;
export const SALE_SER = ["Sale", "Ser"] as const;
export const GST_UQC = ["QTL", "KGS", "BAG"] as const;

export type ItemFormState = {
  commodity_id: string;
  item_code: string;
  name: string;
  item_group: string;
  sub_group: string;
  variety: string;
  rate_per: string;
  bardana_item: string;
  item_type: string;
  having_yield: string;
  paddy: string;
  exempted: string;
  market_fee: string;
  market_pct: string;
  rdf_fee_pct: string;
  grace_days: string;
  bharti: string;
  bardana_req: string;
  hsn_code: string;
  stockable: string;
  tds_required: string;
  gst_type: string;
  gst_type_h_form: string;
  uqc: string;
  text_print_nug: string;
  text_print_wt: string;
  sale_ser: string;
  k_form_reg: string;
  rcm_purchase: string;
  rcm_inv_req: string;
  blocked_itc: string;
  gross_tare_wt_req: string;
  bal_stock_qty_msg: string;
};

export function emptyItemForm(): ItemFormState {
  return {
    commodity_id: "",
    item_code: "",
    name: "",
    item_group: "",
    sub_group: "",
    variety: "",
    rate_per: "Bags",
    bardana_item: "No",
    item_type: "Item",
    having_yield: "No",
    paddy: "No",
    exempted: "No",
    market_fee: "No",
    market_pct: "",
    rdf_fee_pct: "",
    grace_days: "",
    bharti: "",
    bardana_req: "No",
    hsn_code: "",
    stockable: "Yes",
    tds_required: "Yes",
    gst_type: "",
    gst_type_h_form: "",
    uqc: "QTL",
    text_print_nug: "",
    text_print_wt: "",
    sale_ser: "Sale",
    k_form_reg: "No",
    rcm_purchase: "No",
    rcm_inv_req: "No",
    blocked_itc: "No",
    gross_tare_wt_req: "Yes",
    bal_stock_qty_msg: "",
  };
}

export function itemFormFromRecord(row: Record<string, unknown>): ItemFormState {
  const base = emptyItemForm();
  return {
    ...base,
    commodity_id: String(row.commodity_id ?? ""),
    item_code: String(row.item_code ?? ""),
    name: String(row.name ?? ""),
    variety: String(row.variety ?? ""),
    item_group: String(row.item_group ?? ""),
    sub_group: String(row.sub_group ?? ""),
    rate_per: String(row.rate_per ?? row.unit ?? base.rate_per),
    bardana_item: String(row.bardana_item ?? base.bardana_item),
    item_type: String(row.item_type ?? base.item_type),
    having_yield: String(row.having_yield ?? base.having_yield),
    paddy: String(row.paddy ?? base.paddy),
    exempted: String(row.exempted ?? base.exempted),
    market_fee: String(row.market_fee ?? base.market_fee),
    market_pct: String(row.market_pct ?? ""),
    rdf_fee_pct: String(row.rdf_fee_pct ?? ""),
    grace_days: String(row.grace_days ?? ""),
    bharti: String(row.bharti ?? ""),
    bardana_req: String(row.bardana_req ?? base.bardana_req),
    hsn_code: String(row.hsn_code ?? ""),
    stockable: String(row.stockable ?? base.stockable),
    tds_required: String(row.tds_required ?? base.tds_required),
    gst_type: String(row.gst_type ?? ""),
    gst_type_h_form: String(row.gst_type_h_form ?? ""),
    uqc: String(row.uqc ?? base.uqc),
    text_print_nug: String(row.text_print_nug ?? ""),
    text_print_wt: String(row.text_print_wt ?? ""),
    sale_ser: String(row.sale_ser ?? base.sale_ser),
    k_form_reg: String(row.k_form_reg ?? base.k_form_reg),
    rcm_purchase: String(row.rcm_purchase ?? base.rcm_purchase),
    rcm_inv_req: String(row.rcm_inv_req ?? base.rcm_inv_req),
    blocked_itc: String(row.blocked_itc ?? base.blocked_itc),
    gross_tare_wt_req: String(row.gross_tare_wt_req ?? base.gross_tare_wt_req),
    bal_stock_qty_msg: String(row.bal_stock_qty_msg ?? ""),
  };
}

export function itemFormToPayload(form: ItemFormState): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...form, unit: form.rate_per };
  if (form.commodity_id) {
    payload.commodity_id = form.commodity_id;
  }
  return payload;
}
