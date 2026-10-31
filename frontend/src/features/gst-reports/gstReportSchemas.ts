import type { ReportSpec } from "../../app/routing/reportRegistry";

export type GstFilterField =
  | "dateFrom"
  | "dateTo"
  | "returnPeriod"
  | "financialYear"
  | "party"
  | "transactionType"
  | "gstin"
  | "b2bB2c"
  | "itemCrop"
  | "itcEligibility"
  | "invoiceType"
  | "noteType"
  | "hsnCode"
  | "transactionSide"
  | "reconciliationStatus"
  | "gstr2bImport"
  | "itcAction"
  | "reversalRule"
  | "itcCategory"
  | "layoutMode"
  | "consolidate"
  | "groupWise"
  | "showExpDetail"
  | "showDnCn";

export type GstReportSchema = ReportSpec & {
  filters: GstFilterField[];
  showView?: boolean;
  showPreview?: boolean;
  showPrint?: boolean;
  showExcel?: boolean;
  showJsonExport?: boolean;
  showGstr2bImport?: boolean;
  showItemButtons?: boolean;
  f3Label?: string;
  f4Label?: string;
};

const commonDates: GstFilterField[] = ["dateFrom", "dateTo"];

export const gstReportSchemas: Record<string, GstReportSchema> = {
  "Purchase & Sale Summary": {
    reportKey: "gst_purchase_sale_summary",
    needsDates: true,
    filters: [...commonDates, "party", "transactionType"],
    showView: true,
    showPrint: true,
    showExcel: true,
    f3Label: "View",
    f4Label: "Cancel",
  },
  "Bill Wise Sale Detail(GST)": {
    reportKey: "bill_wise_gst_sale",
    needsDates: true,
    filters: [...commonDates, "party", "gstin", "b2bB2c"],
    showView: true,
    showPrint: true,
    showExcel: true,
  },
  "Month Wise Item Wise Sale Report": {
    reportKey: "month_item_wise_sale",
    needsDates: true,
    filters: [
      ...commonDates,
      "itemCrop",
      "layoutMode",
      "consolidate",
      "groupWise",
      "showExpDetail",
      "showDnCn",
    ],
    showPreview: true,
    showView: true,
    showExcel: true,
    showItemButtons: true,
    f3Label: "View F3",
    f4Label: "Cancel F4",
  },
  "Month Wise Item Wise Purchase Report": {
    reportKey: "month_item_wise_purchase",
    needsDates: true,
    filters: [...commonDates, "itemCrop", "layoutMode", "consolidate", "groupWise"],
    showView: true,
    showExcel: true,
    showItemButtons: true,
    f3Label: "View F3",
    f4Label: "Cancel F4",
  },
  "Gst Purchase Detail": {
    reportKey: "gst_purchase_detail",
    needsDates: true,
    filters: [...commonDates, "party", "gstin", "itcEligibility"],
    showView: true,
    showExcel: true,
  },
  "Form GSTR-1(Govt)": {
    reportKey: "gstr1_json",
    needsDates: true,
    jsonExport: true,
    filters: ["returnPeriod", "invoiceType"],
    showView: true,
    showJsonExport: true,
    showExcel: true,
  },
  "GST Debit/Credit Note Report": {
    reportKey: "gst_dn_cn_report",
    needsDates: true,
    filters: [...commonDates, "noteType", "party"],
    showView: true,
    showExcel: true,
  },
  "HSN Wise Sale/Purchase Summary": {
    reportKey: "hsn_wise_summary",
    needsDates: true,
    filters: [...commonDates, "hsnCode", "transactionSide"],
    showView: true,
    showExcel: true,
  },
  "Form GSTR-3B2 Fill": {
    reportKey: "gstr3b_summary",
    needsDates: true,
    filters: ["returnPeriod"],
    showView: true,
    showExcel: true,
  },
  "GSTR-2B Report Auto": {
    reportKey: "gstr2b_report",
    needsDates: true,
    filters: ["returnPeriod", "reconciliationStatus", "gstr2bImport"],
    showView: true,
    showExcel: true,
    showGstr2bImport: true,
  },
  "ITC Reversed & Claimed Report": {
    reportKey: "itc_reversed_report",
    needsDates: true,
    filters: [...commonDates, "itcAction", "reversalRule"],
    showView: true,
    showExcel: true,
  },
  "ITC Availed Report (Capital Goods & Services)": {
    reportKey: "itc_availed_report",
    needsDates: true,
    filters: [...commonDates, "itcCategory"],
    showView: true,
    showExcel: true,
  },
  "Report GSTR-9": {
    reportKey: "gstr9_report",
    needsDates: true,
    filters: ["financialYear"],
    showView: true,
    showExcel: true,
  },
  "Clause 44 Tax Audit Export": {
    reportKey: "clause_44_tax_audit",
    needsDates: true,
    jsonExport: true,
    filters: ["financialYear", ...commonDates],
    showView: true,
    showExcel: true,
    showJsonExport: true,
  },
};

export function resolveGstReportSchema(menuTitle: string, screen: string): GstReportSchema | undefined {
  return gstReportSchemas[menuTitle] ?? gstReportSchemas[screen];
}

export function isGstReportMenuTitle(title: string): boolean {
  return title in gstReportSchemas;
}
