import { FormEvent, useEffect, useMemo, useState } from "react";

import Autocomplete, { LookupItem } from "../../Autocomplete";
import { resolveReportSpec, type ReportSpec } from "../../app/routing/reportRegistry";
import type { Result } from "../../api/types";
import { fuzzyMatch } from "../../utils/fuzzyFilter";

type ReportApi = {
  run_report(reportKey: string, params: Record<string, unknown>): Promise<Result>;
  export_table?(payload: Record<string, unknown>): Promise<Result & { path?: string }>;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function fyStart(): string {
  const now = new Date();
  const year = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return `${year}-04-01`;
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

export default function LegacyReportScreen({
  menuTitle,
  screen,
  onExit,
  api,
}: {
  menuTitle: string;
  screen: string;
  onExit(): void;
  api: ReportApi;
}) {
  const spec: ReportSpec | undefined = resolveReportSpec(menuTitle, screen);
  const displayTitle = menuTitle || screen;
  const [from, setFrom] = useState(fyStart());
  const [to, setTo] = useState(today());
  const [account, setAccount] = useState<LookupItem | null>(null);
  const [commodity, setCommodity] = useState<LookupItem | null>(null);
  const [groupName, setGroupName] = useState("");
  const [annualRate, setAnnualRate] = useState("18");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [status, setStatus] = useState("");
  const [physicalCash, setPhysicalCash] = useState("");

  async function load(event?: FormEvent) {
    event?.preventDefault();
    if (!spec) return;
    if (spec.needsAccount && !account) {
      setResult({ ok: false, error: "Select an account." });
      return;
    }
    if (spec.needsCommodity && !commodity) {
      setResult({ ok: false, error: "Select an item." });
      return;
    }
    const params: Record<string, unknown> = {};
    if (spec.needsDates) {
      params.date_from = from;
      params.date_to = to;
    }
    if (spec.asOfDate) {
      params.as_of_date = to;
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
    if (spec.needsGroup) {
      params.group_name = groupName;
    }
    if (spec.needsRate) {
      params.annual_rate = annualRate;
    }
    if (spec.interestMode) {
      params.interest_mode = spec.interestMode;
    }
    const response = await api.run_report(spec.reportKey, params);
    setResult(response);
    if (response.ok) {
      setStatus(`Report loaded (${flattenRows(response).length} row(s)).`);
    }
  }

  useEffect(() => {
    if (spec && !spec.needsAccount && !spec.needsCommodity) {
      void load();
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        void load();
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const rows = flattenRows(result);
  const columns = rows.length ? Object.keys(rows[0]) : [];
  const filteredRows = useMemo(
    () =>
      rows.filter((row) =>
        fuzzyMatch(query, columns.map((column) => String(row[column] ?? "")).join(" ")),
      ),
    [rows, columns, query],
  );

  const jsonText =
    spec?.jsonExport && result?.ok && typeof result.json === "string" ? result.json : "";

  async function printReport() {
    if (!api.export_table || !rows.length) return;
    const response = await api.export_table({
      format: "pdf",
      title: displayTitle,
      columns,
      rows: filteredRows,
      visible_columns: columns,
    });
    if (response.ok && response.path) setStatus(`Printed PDF → ${response.path}`);
    else setStatus(response.error ?? "Print failed.");
  }

  return (
    <section className="accounts-entry-screen legacy-report-screen">
      <header className="accounts-entry-title">{displayTitle}</header>
      <div className="accounts-entry-toolbar">
        <button type="button" onClick={() => void load()}>
          View F3
        </button>
        <button type="button" onClick={() => void printReport()}>
          Print
        </button>
        <button type="button" onClick={() => void api.export_table?.({ format: "csv", title: displayTitle, columns, rows: filteredRows, visible_columns: columns }).then((r) => r.ok && r.path && setStatus(`Excel → ${r.path}`))}>
          Export Excel
        </button>
        <button type="button" onClick={onExit}>
          Cancel F4
        </button>
      </div>

      <form
        className="legacy-report-filters"
        onSubmit={(event) => {
          void load(event);
        }}
      >
        {spec?.needsDates && (
          <>
            <label>
              Date From
              <input className="picker-field" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </label>
            <label>
              Date To
              <input className="picker-field" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </label>
          </>
        )}
        {spec?.needsAccount && (
          <Autocomplete entityType="account" label="Account" value={account} onSelect={setAccount} />
        )}
        {spec?.needsCommodity && (
          <Autocomplete entityType="commodity" label="Item" value={commodity} onSelect={setCommodity} />
        )}
        {spec?.needsGroup && (
          <label>
            Group / Head
            <input value={groupName} onChange={(e) => setGroupName(e.target.value)} />
          </label>
        )}
        {spec?.needsRate && (
          <label>
            Rate %
            <input inputMode="decimal" value={annualRate} onChange={(e) => setAnnualRate(e.target.value)} />
          </label>
        )}
        {spec?.needsPhysicalCash && (
          <label>
            Physical cash (₹)
            <input type="number" step="0.01" value={physicalCash} onChange={(e) => setPhysicalCash(e.target.value)} />
          </label>
        )}
        <label>
          Search
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter grid…" />
        </label>
      </form>

      {result && !result.ok && <p className="accounts-entry-error">{result.error}</p>}
      {result?.ok && typeof result.difference_paise === "number" && (
        <p className="accounts-entry-status">
          Trial balance difference: ₹{(Number(result.difference_paise) / 100).toFixed(2)}
        </p>
      )}
      {result?.ok && typeof result.net_profit_paise === "number" && (
        <p className="accounts-entry-status">
          Net profit: ₹{(Number(result.net_profit_paise) / 100).toFixed(2)}
        </p>
      )}
      {jsonText && <pre className="legacy-report-json">{jsonText}</pre>}

      <div className="legacy-report-grid-wrap">
        <table className="accounts-entry-grid">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column.replaceAll("_", " ")}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column}>{String(row[column] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {status && <p className="accounts-entry-status">{status}</p>}
    </section>
  );
}
