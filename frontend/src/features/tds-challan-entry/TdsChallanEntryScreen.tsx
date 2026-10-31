import { FormEvent, useEffect, useMemo, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { isoToday } from "../voucher-entry/constants";

type ApiResult = { ok: boolean; error?: string };

type TdsLine = {
  document_charge_id: string;
  selected: boolean;
  document_date: string;
  party_name: string;
  particulars: string;
  amount: string;
  tds: string;
  challan_no: string;
};

type TdsApi = {
  list_tds_challan_deductee_codes?(): Promise<ApiResult & { rows?: string[] }>;
  list_tds_challan_pending_lines?(args: Record<string, string>): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  get_tds_challan_entry?(args: Record<string, string>): Promise<ApiResult & { tds_challan_entry?: Record<string, unknown> }>;
  save_tds_challan_entry?(payload: Record<string, unknown>): Promise<ApiResult & { tds_challan_entry?: Record<string, unknown> }>;
  delete_tds_challan_entry?(challan_id: string): Promise<ApiResult>;
  next_tds_challan_display_id?(): Promise<ApiResult & { challan_display_id?: string }>;
};

function bridge(): TdsApi | undefined {
  return window.pywebview?.api as unknown as TdsApi | undefined;
}

function parseLines(raw: unknown): TdsLine[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((item) => {
    const row = item as Record<string, unknown>;
    return {
      document_charge_id: String(row.document_charge_id ?? ""),
      selected: Boolean(row.selected),
      document_date: String(row.document_date ?? ""),
      party_name: String(row.party_name ?? ""),
      particulars: String(row.particulars ?? ""),
      amount: String(row.amount ?? ""),
      tds: String(row.tds ?? ""),
      challan_no: String(row.challan_no ?? ""),
    };
  });
}

export default function TdsChallanEntryScreen({ mode, onExit }: { mode: "add" | "modify"; onExit(): void }) {
  const title = mode === "add" ? "TDS Challan Entry Add" : "TDS Challan Entry Modify";

  const [challanId, setChallanId] = useState("");
  const [displayId, setDisplayId] = useState("");
  const [challanDate, setChallanDate] = useState(isoToday());
  const [nature, setNature] = useState("");
  const [filterFrom, setFilterFrom] = useState(isoToday());
  const [filterTo, setFilterTo] = useState(isoToday());
  const [deducteeCode, setDeducteeCode] = useState("All");
  const [deducteeOptions, setDeducteeOptions] = useState<string[]>(["All"]);
  const [challanNo, setChallanNo] = useState("");
  const [minorHead, setMinorHead] = useState("200");
  const [bsrCode, setBsrCode] = useState("");
  const [chqNo, setChqNo] = useState("");
  const [lines, setLines] = useState<TdsLine[]>([]);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const totals = useMemo(() => {
    let tds = 0;
    let base = 0;
    for (const line of lines) {
      if (!line.selected) continue;
      tds += Number(line.tds) || 0;
      base += Number(line.amount) || 0;
    }
    return { tds, base };
  }, [lines]);

  useEffect(() => {
    void bridge()?.list_tds_challan_deductee_codes?.().then((response) => {
      if (response?.ok && response.rows?.length) setDeducteeOptions(response.rows);
    });
  }, []);

  useEffect(() => {
    if (mode !== "add") return;
    void bridge()?.next_tds_challan_display_id?.().then((response) => {
      if (response?.ok && response.challan_display_id) setDisplayId(response.challan_display_id);
    });
  }, [mode]);

  function applyRecord(record: Record<string, unknown>) {
    setChallanId(String(record.challan_id ?? ""));
    setDisplayId(String(record.challan_display_id ?? ""));
    setChallanDate(String(record.challan_date ?? isoToday()));
    setNature(String(record.nature ?? ""));
    setFilterFrom(String(record.filter_date_from ?? isoToday()));
    setFilterTo(String(record.filter_date_to ?? isoToday()));
    setDeducteeCode(String(record.deductee_code ?? "All"));
    setChallanNo(String(record.challan_no ?? ""));
    setMinorHead(String(record.minor_head ?? "200"));
    setBsrCode(String(record.bsr_code ?? ""));
    setChqNo(String(record.chq_no ?? ""));
    setLines(parseLines(record.lines));
    setStatus("Challan loaded.");
    setError("");
  }

  async function runShow() {
    const response = await bridge()?.list_tds_challan_pending_lines?.({
      date_from: filterFrom,
      date_to: filterTo,
      deductee_code: deducteeCode,
      challan_id: challanId,
    });
    if (!response?.ok || !response.rows) {
      setError(response?.error ?? "Could not load lines.");
      return;
    }
    setLines(parseLines(response.rows));
    setStatus(`${response.rows.length} line(s) loaded.`);
    setError("");
  }

  async function runFind() {
    const response = await bridge()?.get_tds_challan_entry?.({
      challan_display_id: displayId.trim(),
      challan_date: challanDate,
    });
    if (!response?.ok || !response.tds_challan_entry) {
      setError(response?.error ?? "Challan not found.");
      return;
    }
    applyRecord(response.tds_challan_entry);
  }

  function toggleLine(index: number, selected: boolean) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, selected } : line)));
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const selected = lines.filter((line) => line.selected).map((line) => line.document_charge_id);
    const payload = {
      challan_id: challanId || undefined,
      challan_display_id: displayId,
      challan_date: challanDate,
      nature,
      filter_date_from: filterFrom,
      filter_date_to: filterTo,
      deductee_code: deducteeCode,
      challan_no: challanNo,
      minor_head: minorHead,
      bsr_code: bsrCode,
      chq_no: chqNo,
      total_amt: totals.tds.toFixed(2),
      selected_charge_ids: selected,
    };
    const response = await bridge()?.save_tds_challan_entry?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.tds_challan_entry) applyRecord(response.tds_challan_entry);
    setStatus("Data has been Successfully Saved");
  }

  async function confirmDelete() {
    if (!challanId) return;
    const response = await bridge()?.delete_tds_challan_entry?.(challanId);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    onExit();
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "F3") {
        event.preventDefault();
        void save();
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
      if (event.key === "F5" && mode === "modify") {
        event.preventDefault();
        void runFind();
      }
      if (event.key === "F6" && mode === "modify" && challanId) {
        event.preventDefault();
        setDeleteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <form className="accounts-entry-screen tds-challan-screen" onSubmit={(event) => void save(event)}>
        <header className="accounts-entry-title">{title}</header>
        <div className="accounts-entry-toolbar">
          {mode === "modify" && (
            <>
              <button type="button" onClick={() => void runFind()}>
                Find (F5)
              </button>
              <button type="button" className="danger" onClick={() => setDeleteOpen(true)}>
                Delete (F6)
              </button>
            </>
          )}
          <button type="submit">Save (F3)</button>
          <button type="button" onClick={onExit}>
            Cancel (F4)
          </button>
        </div>

        <div className="tds-challan-fields">
          <label>
            TDS Challan ID
            <input className="highlight-id" readOnly={mode === "add"} value={displayId} onChange={(e) => setDisplayId(e.target.value)} />
          </label>
          <label>
            Challan Date
            <input type="date" value={challanDate} onChange={(e) => setChallanDate(e.target.value)} />
          </label>
          <label className="span-all">
            Nature
            <input value={nature} onChange={(e) => setNature(e.target.value)} />
          </label>
          <label>
            Date From
            <input type="date" value={filterFrom} onChange={(e) => setFilterFrom(e.target.value)} />
          </label>
          <label>
            Date To
            <input type="date" value={filterTo} onChange={(e) => setFilterTo(e.target.value)} />
          </label>
          <label>
            TDS Deductee Co. Code
            <select value={deducteeCode} onChange={(e) => setDeducteeCode(e.target.value)}>
              {deducteeOptions.map((code) => (
                <option key={code}>{code}</option>
              ))}
            </select>
          </label>
          <button type="button" className="show-btn" onClick={() => void runShow()}>
            Show
          </button>
          <label>
            Challan No
            <input value={challanNo} onChange={(e) => setChallanNo(e.target.value)} />
          </label>
          <label>
            Minner Head of Challan
            <select value={minorHead} onChange={(e) => setMinorHead(e.target.value)}>
              <option>200</option>
              <option>400</option>
              <option>800</option>
            </select>
          </label>
          <label>
            BSR Code
            <input value={bsrCode} onChange={(e) => setBsrCode(e.target.value)} />
          </label>
          <label>
            TDS Total Amt
            <input readOnly value={totals.tds.toFixed(2)} />
          </label>
          <label>
            Total Amt
            <input readOnly value={totals.tds.toFixed(2)} />
          </label>
          <label className="span-2">
            Chq. No./DD No.
            <input value={chqNo} onChange={(e) => setChqNo(e.target.value)} />
          </label>
        </div>

        <table className="accounts-entry-grid">
          <thead>
            <tr>
              <th>SNo</th>
              <th>Tick</th>
              <th>Date</th>
              <th>Party Name</th>
              <th>Part</th>
              <th>Amount</th>
              <th>TDS</th>
              <th>Challan No</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={line.document_charge_id || `tds-${index}`}>
                <td>{index + 1}</td>
                <td>
                  <input type="checkbox" checked={line.selected} onChange={(e) => toggleLine(index, e.target.checked)} />
                </td>
                <td>{line.document_date}</td>
                <td>{line.party_name}</td>
                <td>{line.particulars}</td>
                <td>{line.amount}</td>
                <td>{line.tds}</td>
                <td>{line.challan_no}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {status && <p className="accounts-entry-status">{status}</p>}
        {error && <p className="accounts-entry-error">{error}</p>}
      </form>
      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={displayId || challanId}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
