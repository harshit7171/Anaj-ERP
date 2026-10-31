import { FormEvent, useMemo, useState } from "react";

import Autocomplete, { LookupItem } from "../Autocomplete";
import { reportByTitle } from "../reportRegistry";
import type { Result } from "../api/types";
import { fuzzyMatch } from "../utils/fuzzyFilter";

type ReportApi = {
  run_report(reportKey: string, params: Record<string, unknown>): Promise<Result>;
  export_table?(payload: Record<string, unknown>): Promise<Result & { path?: string }>;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function flattenRows(result: Result | null): Record<string, unknown>[] {
  if (!result?.ok) return [];
  if (Array.isArray(result.rows)) return result.rows as Record<string, unknown>[];
  const cashBook = result.cash_book as
    | { receipts?: Record<string, unknown>[]; payments?: Record<string, unknown>[] }
    | undefined;
  if (cashBook) {
    const receipts = (cashBook.receipts ?? []).map((row) => ({ side: "Receipt", ...row }));
    const payments = (cashBook.payments ?? []).map((row) => ({ side: "Payment", ...row }));
    return [...receipts, ...payments];
  }
  const ledger = result.ledger as { entries?: Record<string, unknown>[] } | undefined;
  if (ledger?.entries) return ledger.entries;
  const table31 = (result as { table_3_1?: Record<string, unknown> }).table_3_1;
  if (table31) return [table31];
  const aging = (result as { summary_paise?: Record<string, number> }).summary_paise;
  if (aging) {
    return Object.entries(aging).map(([bucket, paise]) => ({
      bucket,
      balance_paise: paise,
    }));
  }
  if (typeof (result as { variance_paise?: number }).variance_paise === "number") {
    const row = result as Record<string, unknown>;
    return [
      {
        reconcile_date: row.reconcile_date,
        physical_cash_paise: row.physical_cash_paise,
        book_balance_paise: row.book_balance_paise,
        variance_paise: row.variance_paise,
        balanced: row.balanced,
      },
    ];
  }
  return [];
}

function ReportRunner({ title, api }: { title: string; api: ReportApi }) {
  const spec = reportByTitle[title];
  const [from, setFrom] = useState(`${new Date().getFullYear()}-04-01`);
  const [to, setTo] = useState(today());
  const [account, setAccount] = useState<LookupItem | null>(null);
  const [commodity, setCommodity] = useState<LookupItem | null>(null);
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [exportMessage, setExportMessage] = useState("");
  const [hiddenColumns, setHiddenColumns] = useState<Record<string, boolean>>({});
  const [physicalCash, setPhysicalCash] = useState("");

  async function load(event: FormEvent) {
    event.preventDefault();
    if (!spec) return;
    if (spec.needsAccount && !account) {
      setResult({ ok: false, error: "Select an account." });
      return;
    }
    if (spec.needsCommodity && !commodity) {
      setResult({ ok: false, error: "Select a commodity." });
      return;
    }
    const params: Record<string, unknown> = {};
    if (spec.needsDates) {
      params.date_from = from;
      params.date_to = to;
    }
    if (spec.needsAccount && account) {
      params.account_id = account.id;
    }
    if (spec.kachiOnly) {
      params.kachi_only = true;
    }
    if (spec.needsCommodity && commodity) {
      params.commodity_id = commodity.id;
    }
    if (spec.agingAsOf) {
      params.as_of_date = to;
    }
    if (spec.needsPhysicalCash) {
      params.reconcile_date = to;
      params.physical_cash_paise = Math.round(Number(physicalCash || 0) * 100);
    }
    const response = await api.run_report(spec.reportKey, params);
    setResult(response);
  }

  const rows = flattenRows(result);
  const columns = rows.length ? Object.keys(rows[0]) : [];
  const visibleColumns = columns.filter((column) => !hiddenColumns[column]);
  const filteredRows = useMemo(
    () =>
      rows.filter((row) =>
        fuzzyMatch(query, columns.map((column) => String(row[column] ?? "")).join(" ")),
      ),
    [rows, columns, query],
  );

  const jsonText =
    spec?.jsonExport && result?.ok && typeof result.json === "string" ? result.json : "";

  async function exportAs(format: string) {
    if (!api.export_table || !rows.length) return;
    const response = await api.export_table({
      format,
      title,
      columns,
      rows: filteredRows,
      visible_columns: visibleColumns,
    });
    if (response.ok && response.path) {
      setExportMessage(`Exported ${format.toUpperCase()} → ${response.path}`);
    } else {
      setExportMessage(response.error ?? "Export failed");
    }
  }

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden p-2">
      <h2 className="mb-2 text-sm font-semibold">{title}</h2>
      <form className="mb-2 flex flex-wrap items-end gap-2 text-xs" onSubmit={(event) => void load(event)}>
        {spec?.needsDates && (
          <>
            <label>
              From
              <input
                className="rounded border px-1 py-0.5"
                type="date"
                value={from}
                onChange={(event) => setFrom(event.target.value)}
              />
            </label>
            <label>
              To
              <input
                className="rounded border px-1 py-0.5"
                type="date"
                value={to}
                onChange={(event) => setTo(event.target.value)}
              />
            </label>
          </>
        )}
        {spec?.needsAccount && (
          <Autocomplete entityType="account" label="Account" value={account} onSelect={setAccount} />
        )}
        {spec?.needsCommodity && (
          <Autocomplete entityType="commodity" label="Item" value={commodity} onSelect={setCommodity} />
        )}
        {spec?.needsPhysicalCash && (
          <label>
            Physical cash (₹)
            <input
              className="rounded border px-1 py-0.5"
              type="number"
              step="0.01"
              value={physicalCash}
              onChange={(event) => setPhysicalCash(event.target.value)}
            />
          </label>
        )}
        <input
          className="rounded border px-2 py-0.5"
          placeholder="Search..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit">Run</button>
      </form>
      {rows.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1 text-[10px]">
          {["csv", "xlsx", "pdf", "docx", "xml", "html", "png", "jpeg"].map((format) => (
            <button key={format} type="button" onClick={() => void exportAs(format)}>
              Export {format.toUpperCase()}
            </button>
          ))}
        </div>
      )}
      {exportMessage && <p className="mb-1 text-[10px] text-[#0f766e]">{exportMessage}</p>}
      {columns.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2 text-[10px]">
          {columns.map((column) => (
            <label className="checkbox-label" key={column}>
              <input
                checked={!hiddenColumns[column]}
                type="checkbox"
                onChange={() =>
                  setHiddenColumns((current) => ({
                    ...current,
                    [column]: !current[column],
                  }))
                }
              />
              {column.replaceAll("_", " ")}
            </label>
          ))}
        </div>
      )}
      {result && !result.ok && <p className="text-xs text-red-700">{result.error}</p>}
      {result?.ok && typeof result.net_profit_paise === "number" && (
        <p className="mb-1 text-xs font-semibold">
          Net profit: ₹{(Number(result.net_profit_paise) / 100).toFixed(2)}
        </p>
      )}
      {result?.ok && typeof result.net_tax_payable_paise === "number" && (
        <p className="mb-1 text-xs font-semibold">
          Net tax payable: ₹{(Number(result.net_tax_payable_paise) / 100).toFixed(2)}
        </p>
      )}
      {jsonText && (
        <pre className="mb-2 max-h-48 overflow-auto rounded border bg-slate-50 p-2 text-[10px]">
          {jsonText}
        </pre>
      )}
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              {visibleColumns.map((column) => (
                <th className="border px-1 py-0.5 text-left" key={column}>
                  {column.replaceAll("_", " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row, index) => (
              <tr key={index}>
                {visibleColumns.map((column) => (
                  <td className="border px-1 py-0.5" key={column}>
                    {String(row[column] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default ReportRunner;
