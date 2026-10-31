/** @deprecated Use gstReportSchemas — kept for reportRegistry compatibility. */
export type { GstReportSchema as GstReportUiConfig } from "./gstReportSchemas";
export {
  gstReportSchemas as gstReportConfigByTitle,
  isGstReportMenuTitle,
  resolveGstReportSchema as resolveGstReportConfig,
} from "./gstReportSchemas";

export const GST_REPORT_MENU_TITLES = [
  "Purchase & Sale Summary",
  "Bill Wise Sale Detail(GST)",
  "Month Wise Item Wise Sale Report",
  "Month Wise Item Wise Purchase Report",
  "Gst Purchase Detail",
  "Form GSTR-1(Govt)",
  "GST Debit/Credit Note Report",
  "HSN Wise Sale/Purchase Summary",
  "Form GSTR-3B2 Fill",
  "GSTR-2B Report Auto",
  "ITC Reversed & Claimed Report",
  "ITC Availed Report (Capital Goods & Services)",
  "Report GSTR-9",
  "Clause 44 Tax Audit Export",
] as const;
