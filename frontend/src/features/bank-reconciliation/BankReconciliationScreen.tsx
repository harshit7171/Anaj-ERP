import { useEffect, useState } from "react";

import { isoToday } from "../voucher-entry/constants";

type ApiResult = { ok: boolean; error?: string; path?: string };

type ReconRow = {
  voucher_line_id: string;
  voucher_date: string;
  voucher_type: string;
  voucher_number: string;
  bank_name: string;
  debit: string;
  credit: string;
  particulars: string;
  cheque_no: string;
  reconciled: boolean;
};

type ReconApi = {
  search_bank_reconciliation?(payload: Record<string, unknown>): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  set_bank_reconciliation?(ids: string[], reconciled: boolean): Promise<ApiResult>;
  export_bank_reconciliation?(payload: Record<string, unknown>): Promise<ApiResult & { path?: string }>;
  print_bank_reconciliation?(payload: Record<string, unknown>): Promise<ApiResult>;
};

function bridge(): ReconApi | undefined {
  return window.pywebview?.api as unknown as ReconApi | undefined;
}

function fyStart(): string {
  const today = new Date();
  const year = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
  return `${year}-04-01`;
}

function parseRows(raw: unknown): ReconRow[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => {
    const row = item as Record<string, unknown>;
    return {
      voucher_line_id: String(row.voucher_line_id ?? ""),
      voucher_date: String(row.voucher_date ?? ""),
      voucher_type: String(row.voucher_type ?? ""),
      voucher_number: String(row.voucher_number ?? ""),
      bank_name: String(row.bank_name ?? ""),
      debit: String(row.debit ?? ""),
      credit: String(row.credit ?? ""),
      particulars: String(row.particulars ?? ""),
      cheque_no: String(row.cheque_no ?? ""),
      reconciled: Boolean(row.reconciled),
    };
  });
}

export default function BankReconciliationScreen({ onExit }: { onExit(): void }) {
  const [dateFrom, setDateFrom] = useState(fyStart());
  const [dateTo, setDateTo] = useState(isoToday());
  const [debitCredit, setDebitCredit] = useState("B");
  const [reconciledFilter, setReconciledFilter] = useState("B");
  const [bankName, setBankName] = useState("");
  const [amountEq, setAmountEq] = useState("");
  const [amountGte, setAmountGte] = useState("");
  const [amountLte, setAmountLte] = useState("");
  const [particulars, setParticulars] = useState("");
  const [chequeNo, setChequeNo] = useState("");
  const [rows, setRows] = useState<ReconRow[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  function filtersPayload(): Record<string, unknown> {
    return {
      date_from: dateFrom,
      date_to: dateTo,
      debit_credit: debitCredit,
      reconciled_filter: reconciledFilter,
      bank_name: bankName,
      amount_eq: amountEq,
      amount_gte: amountGte,
      amount_lte: amountLte,
      particulars,
      cheque_no: chequeNo,
    };
  }

  async function runSearch() {
    setError("");
    const response = await bridge()?.search_bank_reconciliation?.(filtersPayload());
    if (!response?.ok) {
      setError(response?.error ?? "Search failed.");
      return;
    }
    setRows(parseRows(response.rows));
    setStatus(`${response.rows?.length ?? 0} row(s).`);
  }

  useEffect(() => {
    void runSearch();
  }, []);

  async function toggleReconciled(row: ReconRow) {
    const response = await bridge()?.set_bank_reconciliation?.([row.voucher_line_id], !row.reconciled);
    if (!response?.ok) {
      setError(response?.error ?? "Update failed.");
      return;
    }
    void runSearch();
  }

  async function exportExcel() {
    const response = await bridge()?.export_bank_reconciliation?.(filtersPayload());
    if (!response?.ok) {
      setError(response?.error ?? "Export failed.");
      return;
    }
    setStatus(response.path ? `Exported to ${response.path}` : "Exported.");
  }

  async function printReport() {
    const response = await bridge()?.print_bank_reconciliation?.(filtersPayload());
    if (!response?.ok) setError(response?.error ?? "Print failed.");
    else setStatus("Sent to printer.");
  }

  return (
    <section className="accounts-entry-screen bank-recon-screen">
      <header className="accounts-entry-title">Bank Reconsilation</header>
      <div className="accounts-entry-toolbar">
        <button type="button" onClick={() => void exportExcel()}>
          Export to Excel
        </button>
        <button type="button" onClick={() => void printReport()}>
          Print
        </button>
        <button type="button" onClick={onExit}>
          Exit
        </button>
      </div>

      <div className="bank-recon-filters">
        <label>
          Date From
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          Date To
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <label>
          Debit/Credit/Both
          <select value={debitCredit} onChange={(e) => setDebitCredit(e.target.value)}>
            <option value="B">B</option>
            <option value="D">D</option>
            <option value="C">C</option>
          </select>
        </label>
        <label>
          Reconciled/Non/Both
          <select value={reconciledFilter} onChange={(e) => setReconciledFilter(e.target.value)}>
            <option value="B">B</option>
            <option value="R">R</option>
            <option value="N">N</option>
          </select>
        </label>
        <label className="span-2">
          Bank Name
          <input value={bankName} onChange={(e) => setBankName(e.target.value)} />
        </label>
        <label>
          Amount =
          <input inputMode="decimal" value={amountEq} onChange={(e) => setAmountEq(e.target.value)} />
        </label>
        <label>
          Amount &gt;=
          <input inputMode="decimal" value={amountGte} onChange={(e) => setAmountGte(e.target.value)} />
        </label>
        <label>
          Amount &lt;=
          <input inputMode="decimal" value={amountLte} onChange={(e) => setAmountLte(e.target.value)} />
        </label>
        <label className="span-2">
          Particulars
          <input value={particulars} onChange={(e) => setParticulars(e.target.value)} />
        </label>
        <label>
          Search Chque
          <input value={chequeNo} onChange={(e) => setChequeNo(e.target.value)} />
        </label>
        <button type="button" className="show-btn" onClick={() => void runSearch()}>
          Search
        </button>
      </div>

      <table className="accounts-entry-grid bank-recon-grid">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Voucher</th>
            <th>Bank</th>
            <th>Debit</th>
            <th>Credit</th>
            <th>Particulars</th>
            <th>Cheque</th>
            <th>Reconciled</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.voucher_line_id}>
              <td>{row.voucher_date}</td>
              <td>{row.voucher_type}</td>
              <td>{row.voucher_number}</td>
              <td>{row.bank_name}</td>
              <td>{row.debit}</td>
              <td>{row.credit}</td>
              <td>{row.particulars}</td>
              <td>{row.cheque_no}</td>
              <td>
                <input type="checkbox" checked={row.reconciled} onChange={() => void toggleReconciled(row)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {status && <p className="accounts-entry-status">{status}</p>}
      {error && <p className="accounts-entry-error">{error}</p>}
    </section>
  );
}
