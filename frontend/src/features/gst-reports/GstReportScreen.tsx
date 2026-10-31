import { useEffect, useMemo, useState } from "react";

import Autocomplete, { LookupItem } from "../../Autocomplete";
import type { Result } from "../../api/types";
import { fuzzyMatch } from "../../utils/fuzzyFilter";
import { resolveGstReportSchema, type GstReportSchema } from "./gstReportSchemas";

type GstReportApi = {
  run_report(reportKey: string, params: Record<string, unknown>): Promise<Result>;
  export_table?(payload: Record<string, unknown>): Promise<Result & { path?: string }>;
  lookup_gst_report_items?(query?: string): Promise<Result & { rows?: Record<string, unknown>[] }>;
  lookup_gst_report_item_groups?(query?: string): Promise<Result & { rows?: Record<string, unknown>[] }>;
  select_gstr2b_json_file?(): Promise<
    Result & { file_path?: string; invoice_count?: number; cancelled?: boolean }
  >;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function fyStart(): string {
  const now = new Date();
  const year = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return `${year}-04-01`;
}

function fyEnd(): string {
  const now = new Date();
  const year = now.getMonth() >= 3 ? now.getFullYear() + 1 : now.getFullYear();
  return `${year}-03-31`;
}

function currentReturnPeriod(): string {
  return today().slice(0, 7);
}

function flattenRows(result: Result | null, schema?: GstReportSchema): Record<string, unknown>[] {
  if (!result?.ok) return [];
  if (Array.isArray(result.rows)) return result.rows as Record<string, unknown>[];
  return [];
}

function resolveColumns(result: Result | null, rows: Record<string, unknown>[]): string[] {
  const fromApi = (result as { columns?: string[] })?.columns;
  if (fromApi?.length) return fromApi;
  if (rows.length) return Object.keys(rows[0]);
  return [];
}

export default function GstReportScreen({
  menuTitle,
  screen,
  onExit,
  api,
}: {
  menuTitle: string;
  screen: string;
  onExit(): void;
  api: GstReportApi;
}) {
  const schema: GstReportSchema | undefined = resolveGstReportSchema(menuTitle, screen);
  const title = menuTitle || screen;

  const [dateFrom, setDateFrom] = useState(fyStart());
  const [dateTo, setDateTo] = useState(today());
  const [returnPeriod, setReturnPeriod] = useState(currentReturnPeriod());
  const [financialYearLabel, setFinancialYearLabel] = useState(() => {
    const startYear = new Date(fyStart()).getFullYear();
    return `${startYear}-${startYear + 1}`;
  });
  const [party, setParty] = useState<LookupItem | null>(null);
  const [transactionType, setTransactionType] = useState("all");
  const [gstinQuery, setGstinQuery] = useState("");
  const [b2bB2c, setB2bB2c] = useState("all");
  const [itemCrop, setItemCrop] = useState("");
  const [commodityId, setCommodityId] = useState("");
  const [itemGroup, setItemGroup] = useState("");
  const [layoutMode, setLayoutMode] = useState("M");
  const [consolidate, setConsolidate] = useState("N");
  const [groupWise, setGroupWise] = useState("Y");
  const [showExpDetail, setShowExpDetail] = useState("N");
  const [showDnCn, setShowDnCn] = useState("Y");
  const [itcEligibility, setItcEligibility] = useState("all");
  const [invoiceType, setInvoiceType] = useState("all");
  const [noteType, setNoteType] = useState("both");
  const [hsnCode, setHsnCode] = useState("");
  const [transactionSide, setTransactionSide] = useState("both");
  const [reconciliationStatus, setReconciliationStatus] = useState("all");
  const [gstr2bFilePath, setGstr2bFilePath] = useState("");
  const [taxTolerancePaise, setTaxTolerancePaise] = useState("100");
  const [itcAction, setItcAction] = useState("both");
  const [reversalRule, setReversalRule] = useState("all");
  const [itcCategory, setItcCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [picker, setPicker] = useState<{ kind: "item" | "group"; rows: Record<string, unknown>[] } | null>(
    null,
  );

  function buildParams(): Record<string, unknown> {
    const useReturnPeriod = schema?.filters.includes("returnPeriod");
    const useFyOnly = schema?.filters.includes("financialYear") && !schema.filters.includes("dateFrom");
    let from = dateFrom;
    let to = dateTo;
    if (useReturnPeriod) {
      from = `${returnPeriod}-01`;
      const [y, m] = returnPeriod.split("-").map(Number);
      const last = new Date(y, m, 0).getDate();
      to = `${returnPeriod}-${String(last).padStart(2, "0")}`;
    }
    if (useFyOnly && schema?.filters.length === 1) {
      from = fyStart();
      to = fyEnd();
    }
    return {
      date_from: from,
      date_to: to,
      return_period: returnPeriod,
      financial_year: financialYearLabel,
      party_id: party?.id ?? "",
      transaction_type: transactionType,
      gstin_query: gstinQuery,
      b2b_b2c: b2bB2c,
      commodity_id: commodityId,
      item_crop: itemCrop,
      item_query: itemCrop,
      agricultural_group: itemGroup,
      item_group: itemGroup,
      layout_mode: layoutMode,
      show_item_month_wise: layoutMode,
      consolidate,
      group_wise: groupWise,
      show_group_wise: groupWise,
      show_exp_detail: showExpDetail,
      show_dn_cn: showDnCn,
      itc_eligibility: itcEligibility,
      invoice_type: invoiceType,
      note_type: noteType,
      hsn_code: hsnCode,
      transaction: transactionSide,
      reconciliation_status: reconciliationStatus,
      gstr2b_file_path: gstr2bFilePath,
      tax_tolerance_paise: Number(taxTolerancePaise || 100),
      itc_action: itcAction,
      reversal_rule: reversalRule,
      itc_category: itcCategory,
    };
  }

  async function runReport(previewOnly = false) {
    if (!schema) return;
    setError("");
    const response = await api.run_report(schema.reportKey, buildParams());
    setResult(response);
    if (!response.ok) {
      setError(response.error ?? "Report failed.");
      return;
    }
    const count = flattenRows(response, schema).length;
    setStatus(previewOnly ? `Preview: ${count} row(s).` : `View: ${count} row(s).`);
  }

  async function openItemPicker() {
    const response = await api.lookup_gst_report_items?.(itemCrop);
    if (response?.ok && response.rows) setPicker({ kind: "item", rows: response.rows });
  }

  async function openGroupPicker() {
    const response = await api.lookup_gst_report_item_groups?.(itemGroup || itemCrop);
    if (response?.ok && response.rows) setPicker({ kind: "group", rows: response.rows });
  }

  async function importGstr2bJson() {
    setError("");
    const response = await api.select_gstr2b_json_file?.();
    if (!response?.ok) {
      setError(response?.error ?? "Could not load GSTR-2B JSON.");
      return;
    }
    if (response.cancelled) {
      setStatus("Import cancelled.");
      return;
    }
    if (response.file_path) {
      setGstr2bFilePath(response.file_path);
      setStatus(
        `Loaded GSTR-2B: ${response.invoice_count ?? 0} invoice(s) from ${response.file_path}`,
      );
    }
  }

  function applyPicker(row: Record<string, unknown>) {
    if (!picker) return;
    if (picker.kind === "item") {
      setCommodityId(String(row.commodity_id ?? ""));
      setItemCrop(String(row.item_name ?? ""));
    } else {
      setItemGroup(String(row.group_name ?? ""));
    }
    setPicker(null);
  }

  async function exportTable(format: "csv" | "pdf") {
    const rows = flattenRows(result, schema);
    const columns = resolveColumns(result, rows);
    if (!rows.length || !api.export_table) return;
    const response = await api.export_table({
      format,
      title,
      columns,
      rows,
      visible_columns: columns,
    });
    if (response.ok && response.path) {
      setStatus(format === "pdf" ? `Print → ${response.path}` : `Excel → ${response.path}`);
    }
  }

  async function exportJson() {
    const json = (result as { json?: string })?.json;
    if (!json || !api.export_table) return;
    const response = await api.export_table({
      format: "csv",
      title: `${title} JSON`,
      columns: ["json"],
      rows: [{ json }],
      visible_columns: ["json"],
    });
    if (response.ok && response.path) setStatus(`JSON export → ${response.path}`);
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        void runReport(false);
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const rows = flattenRows(result, schema);
  const columns = resolveColumns(result, rows);
  const footer = (result as { footer?: Record<string, string> })?.footer;
  const reconSummary = (result as { summary?: Record<string, number> })?.summary;

  const filteredRows = useMemo(() => {
    let next = rows;
    if (schema?.showGstr2bImport && reconciliationStatus !== "all") {
      const bucketByFilter: Record<string, string> = {
        matched: "matched",
        probable: "probable_match",
        mismatched: "probable_match",
        in_books_not_in_2b: "in_books_not_in_2b",
        in_2b_not_in_books: "in_2b_not_in_books",
        missing: "in_2b_not_in_books",
      };
      const bucket = bucketByFilter[reconciliationStatus];
      if (bucket && reconciliationStatus !== "missing") {
        next = next.filter((row) => String(row.status_bucket ?? "") === bucket);
      }
      if (reconciliationStatus === "missing") {
        next = next.filter((row) =>
          ["in_books_not_in_2b", "in_2b_not_in_books"].includes(String(row.status_bucket ?? "")),
        );
      }
    }
    return next.filter((row) =>
      fuzzyMatch(query, columns.map((column) => String(row[column] ?? "")).join(" ")),
    );
  }, [rows, columns, query, reconciliationStatus, schema?.showGstr2bImport]);

  function reconRowClass(row: Record<string, unknown>): string {
    const bucket = String(row.status_bucket ?? "");
    if (bucket === "matched") return "gst-recon-row gst-recon-row--matched";
    if (bucket === "probable_match") return "gst-recon-row gst-recon-row--probable";
    if (bucket === "in_books_not_in_2b" || bucket === "in_2b_not_in_books") {
      return "gst-recon-row gst-recon-row--missing";
    }
    return "gst-recon-row";
  }

  const jsonText =
    schema?.jsonExport && result?.ok && typeof (result as unknown as { json?: string }).json === "string"
      ? (result as unknown as { json: string }).json
      : "";

  if (!schema) {
    return (
      <section className="accounts-entry-screen">
        <p className="accounts-entry-error">Unknown GST report: {title}</p>
        <button type="button" onClick={onExit}>
          Close F4
        </button>
      </section>
    );
  }

  const filters = schema.filters;

  return (
    <>
      <section className="accounts-entry-screen gst-report-screen">
        <header className="accounts-entry-title">{title}</header>

        <div className="gst-report-filters">
          {filters.includes("dateFrom") && (
            <label>
              Date From
              <input
                className="picker-field"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </label>
          )}
          {filters.includes("dateTo") && (
            <label>
              Date To
              <input
                className="picker-field"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </label>
          )}
          {filters.includes("returnPeriod") && (
            <label>
              Return Period
              <input
                className="picker-field"
                type="month"
                value={returnPeriod}
                onChange={(e) => setReturnPeriod(e.target.value)}
              />
            </label>
          )}
          {filters.includes("financialYear") && (
            <label>
              Financial Year
              <input
                className="picker-field"
                value={financialYearLabel}
                onChange={(e) => {
                  setFinancialYearLabel(e.target.value);
                  const match = /^(\d{4})-(\d{4})$/.exec(e.target.value.trim());
                  if (match) {
                    setDateFrom(`${match[1]}-04-01`);
                    setDateTo(`${match[2]}-03-31`);
                  }
                }}
              />
            </label>
          )}
          {filters.includes("party") && (
            <Autocomplete
              entityType="party"
              label="Account/Party Name"
              value={party}
              onSelect={setParty}
            />
          )}
          {filters.includes("transactionType") && (
            <label>
              Transaction Type
              <select value={transactionType} onChange={(e) => setTransactionType(e.target.value)}>
                <option value="all">All</option>
                <option value="purchase">Purchase</option>
                <option value="sale">Sale</option>
              </select>
            </label>
          )}
          {filters.includes("gstin") && (
            <label>
              GSTIN
              <input className="picker-field" value={gstinQuery} onChange={(e) => setGstinQuery(e.target.value)} />
            </label>
          )}
          {filters.includes("b2bB2c") && (
            <label>
              B2B/B2C
              <select value={b2bB2c} onChange={(e) => setB2bB2c(e.target.value)}>
                <option value="all">All</option>
                <option value="b2b">B2B</option>
                <option value="b2c">B2C</option>
              </select>
            </label>
          )}
          {filters.includes("itemCrop") && (
            <label className="gst-item-crop">
              Item\Crop
              <input
                className="picker-field"
                value={itemCrop}
                onChange={(e) => {
                  setItemCrop(e.target.value);
                  setCommodityId("");
                }}
                onDoubleClick={() => void openItemPicker()}
              />
            </label>
          )}
          {filters.includes("itcEligibility") && (
            <label>
              ITC Eligibility
              <select value={itcEligibility} onChange={(e) => setItcEligibility(e.target.value)}>
                <option value="all">All</option>
                <option value="eligible">Eligible</option>
                <option value="ineligible">Ineligible</option>
              </select>
            </label>
          )}
          {filters.includes("invoiceType") && (
            <label>
              Invoice Type
              <select value={invoiceType} onChange={(e) => setInvoiceType(e.target.value)}>
                <option value="all">All</option>
                <option value="b2b">B2B</option>
                <option value="b2c_large">B2C Large</option>
                <option value="b2c_small">B2C Small</option>
                <option value="export">Export</option>
                <option value="nil">Nil Rated</option>
              </select>
            </label>
          )}
          {filters.includes("noteType") && (
            <label>
              Note Type
              <select value={noteType} onChange={(e) => setNoteType(e.target.value)}>
                <option value="both">Both</option>
                <option value="debit">Debit Note</option>
                <option value="credit">Credit Note</option>
              </select>
            </label>
          )}
          {filters.includes("hsnCode") && (
            <label>
              HSN/SAC Code
              <input className="picker-field" value={hsnCode} onChange={(e) => setHsnCode(e.target.value)} />
            </label>
          )}
          {filters.includes("transactionSide") && (
            <label>
              Transaction
              <select value={transactionSide} onChange={(e) => setTransactionSide(e.target.value)}>
                <option value="both">Both</option>
                <option value="sale">Sale</option>
                <option value="purchase">Purchase</option>
              </select>
            </label>
          )}
          {filters.includes("reconciliationStatus") && (
            <label>
              Reconciliation Status
              <select value={reconciliationStatus} onChange={(e) => setReconciliationStatus(e.target.value)}>
                <option value="all">All</option>
                <option value="matched">Matched (Green)</option>
                <option value="probable">Probable Match (Yellow)</option>
                <option value="in_books_not_in_2b">In Books, Not in 2B (Red)</option>
                <option value="in_2b_not_in_books">In 2B, Not in Books (Red)</option>
                <option value="missing">Any Red (both)</option>
              </select>
            </label>
          )}
          {filters.includes("gstr2bImport") && (
            <>
              <label className="gst-report-file-label">
                GSTR-2B JSON
                <input className="picker-field" readOnly value={gstr2bFilePath || "Not loaded"} />
              </label>
              <label>
                Tax tolerance (paise)
                <input
                  className="picker-field"
                  inputMode="numeric"
                  value={taxTolerancePaise}
                  onChange={(e) => setTaxTolerancePaise(e.target.value)}
                />
              </label>
            </>
          )}
          {filters.includes("itcAction") && (
            <label>
              Action
              <select value={itcAction} onChange={(e) => setItcAction(e.target.value)}>
                <option value="both">Both</option>
                <option value="reversed">Reversed</option>
                <option value="claimed">Claimed</option>
              </select>
            </label>
          )}
          {filters.includes("reversalRule") && (
            <label>
              Reversal Rule
              <select value={reversalRule} onChange={(e) => setReversalRule(e.target.value)}>
                <option value="all">All</option>
                <option value="Rule 38">Rule 38</option>
                <option value="Rule 42">Rule 42</option>
                <option value="Rule 43">Rule 43</option>
                <option value="Section 17(5)">Section 17(5)</option>
              </select>
            </label>
          )}
          {filters.includes("itcCategory") && (
            <label>
              ITC Category
              <select value={itcCategory} onChange={(e) => setItcCategory(e.target.value)}>
                <option value="all">All</option>
                <option value="inputs">Inputs</option>
                <option value="capital goods">Capital Goods</option>
                <option value="input services">Input Services</option>
              </select>
            </label>
          )}

          <div className="gst-report-actions">
            {schema.showItemButtons && (
              <>
                <button type="button" onClick={() => void openItemPicker()}>
                  Items
                </button>
                <button type="button" onClick={() => void openGroupPicker()}>
                  Item Group
                </button>
              </>
            )}
            {schema.showPreview && (
              <button type="button" onClick={() => void runReport(true)}>
                PreView
              </button>
            )}
            {schema.showView !== false && (
              <button type="button" className="accent-btn" onClick={() => void runReport(false)}>
                {schema.f3Label ?? "View F3"}
              </button>
            )}
            {schema.showPrint && (
              <button type="button" onClick={() => void exportTable("pdf")}>
                Print
              </button>
            )}
            {schema.showExcel !== false && (
              <button type="button" className="excel-btn" onClick={() => void exportTable("csv")}>
                Excel
              </button>
            )}
            {schema.showJsonExport && (
              <button type="button" onClick={() => void exportJson()}>
                JSON Export
              </button>
            )}
            {schema.showGstr2bImport && (
              <button type="button" onClick={() => void importGstr2bJson()}>
                Import 2B JSON
              </button>
            )}
            <button type="button" onClick={onExit}>
              {schema.f4Label ?? "Cancel F4"}
            </button>
          </div>
        </div>

        <div className="gst-report-toggles">
          {filters.includes("layoutMode") && (
            <label>
              Show Item/Month Wise
              <select className="picker-field" value={layoutMode} onChange={(e) => setLayoutMode(e.target.value)}>
                <option value="M">M</option>
                <option value="I">I</option>
              </select>
            </label>
          )}
          {filters.includes("consolidate") && (
            <label>
              Consolidate
              <select value={consolidate} onChange={(e) => setConsolidate(e.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
          )}
          {filters.includes("groupWise") && (
            <label>
              Show Group Wise
              <select value={groupWise} onChange={(e) => setGroupWise(e.target.value)}>
                <option value="Y">Y</option>
                <option value="N">N</option>
              </select>
            </label>
          )}
          {filters.includes("showExpDetail") && (
            <label>
              Show Exp. Detail
              <select value={showExpDetail} onChange={(e) => setShowExpDetail(e.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
          )}
          {filters.includes("showDnCn") && (
            <label>
              Show DN/CN
              <select value={showDnCn} onChange={(e) => setShowDnCn(e.target.value)}>
                <option value="Y">Y</option>
                <option value="N">N</option>
              </select>
            </label>
          )}
        </div>

        {result?.ok &&
          typeof (result as unknown as { net_tax_payable_paise?: number }).net_tax_payable_paise ===
            "number" && (
          <p className="accounts-entry-status">
            Net tax payable: ₹
            {(
              Number((result as unknown as { net_tax_payable_paise: number }).net_tax_payable_paise) / 100
            ).toFixed(2)}
          </p>
        )}
        {error && <p className="accounts-entry-error">{error}</p>}
        {schema.showGstr2bImport && reconSummary && (
          <p className="accounts-entry-status gst-recon-summary">
            Matched {reconSummary.matched ?? 0} · Probable {reconSummary.probable_match ?? 0} · In books
            only {reconSummary.in_books_not_in_2b ?? 0} · In 2B only {reconSummary.in_2b_not_in_books ?? 0}
          </p>
        )}
        {jsonText && <pre className="legacy-report-json">{jsonText}</pre>}

        <div className="legacy-report-grid-wrap gst-report-viewer">
          <table className="accounts-entry-grid gst-recon-grid">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row, index) => (
                <tr key={index} className={schema.showGstr2bImport ? reconRowClass(row) : undefined}>
                  {columns.map((column) => (
                    <td key={column}>
                      {column === "Document Id" && row[column] ? (
                        <button
                          className="gst-recon-doc-link"
                          type="button"
                          title="Copy document id for Modify / audit"
                          onClick={() => {
                            void navigator.clipboard?.writeText(String(row[column]));
                            setStatus(`Copied document id ${String(row[column])}`);
                          }}
                        >
                          {String(row[column])}
                        </button>
                      ) : (
                        String(row[column] ?? "")
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
            {footer && (
              <tfoot>
                <tr className="gst-report-footer">
                  <td colSpan={Math.max(1, columns.length - 3)}>Totals</td>
                  <td>{footer["Taxable Amount"] ?? ""}</td>
                  <td>{footer.Taxes ?? ""}</td>
                  <td>{footer["Grand Total"] ?? ""}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
        <label className="gst-grid-search">
          Search
          <input value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        {status && <p className="accounts-entry-status">{status}</p>}
      </section>

      {picker && (
        <div className="accounts-picker-overlay">
          <div className="accounts-picker-panel">
            <header>Select {picker.kind === "item" ? "item" : "group"}</header>
            <ul>
              {picker.rows.map((row, index) => (
                <li key={index}>
                  <button type="button" onClick={() => applyPicker(row)}>
                    {String(row.item_name ?? row.group_name ?? "")}
                  </button>
                </li>
              ))}
            </ul>
            <button type="button" onClick={() => setPicker(null)}>
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
