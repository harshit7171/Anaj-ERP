import { FormEvent, useEffect, useState } from "react";

import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import { isoToday } from "../voucher-entry/constants";

type ApiResult = { ok: boolean; error?: string };

type AdjLine = {
  commodity_id: string;
  item_name: string;
  cur_qty: string;
  cur_wt: string;
  issue_qty: string;
  issue_wt: string;
  rec_qty: string;
  rec_wt: string;
  remarks: string;
};

function emptyLine(): AdjLine {
  return {
    commodity_id: "",
    item_name: "",
    cur_qty: "",
    cur_wt: "",
    issue_qty: "",
    issue_wt: "",
    rec_qty: "",
    rec_wt: "",
    remarks: "",
  };
}

type AdjApi = {
  save_stock_adjustment?(payload: Record<string, unknown>): Promise<ApiResult & { stock_adjustment?: Record<string, unknown> }>;
  get_stock_adjustment_entry?(args: Record<string, string>): Promise<ApiResult & { stock_adjustment?: Record<string, unknown> }>;
  next_stock_adjustment_number?(): Promise<ApiResult & { ref_no?: string }>;
  lookup_stock_adjustment_items?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  stock_adjustment_line_hints?(commodity_id: string, godown?: string): Promise<ApiResult & { hints?: Record<string, string> }>;
};

function bridge(): AdjApi | undefined {
  return window.pywebview?.api as unknown as AdjApi | undefined;
}

export default function StockAdjustmentScreen({ mode, onExit }: { mode: "add" | "modify"; onExit(): void }) {
  const title = mode === "add" ? "Stock Adjustment Add" : "Stock Adjustment Modify";
  const [adjustmentId, setAdjustmentId] = useState("");
  const [date, setDate] = useState(isoToday());
  const [stkNo, setStkNo] = useState("");
  const [godown, setGodown] = useState("Main");
  const [lines, setLines] = useState<AdjLine[]>([emptyLine()]);
  const [picker, setPicker] = useState<{ index: number; rows: Record<string, unknown>[] } | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const handleGridEnter = useGridEnterNavigation(() => {
    setLines((prev) => [...prev, emptyLine()]);
    return false;
  });

  useEffect(() => {
    if (mode !== "add") return;
    void bridge()?.next_stock_adjustment_number?.().then((response) => {
      if (response?.ok && response.ref_no) setStkNo(response.ref_no);
    });
  }, [mode]);

  function applyRecord(record: Record<string, unknown>) {
    setAdjustmentId(String(record.adjustment_id ?? ""));
    setDate(String(record.adjustment_date ?? isoToday()));
    setStkNo(String(record.ref_no ?? ""));
    setGodown(String(record.godown ?? "Main"));
    const raw = record.lines;
    if (Array.isArray(raw) && raw.length) {
      setLines(
        raw.map((item) => {
          const row = item as Record<string, unknown>;
          return {
            commodity_id: String(row.commodity_id ?? ""),
            item_name: String(row.item_name ?? ""),
            cur_qty: String(row.cur_qty ?? ""),
            cur_wt: String(row.cur_wt ?? ""),
            issue_qty: String(row.issue_qty ?? ""),
            issue_wt: String(row.issue_wt ?? ""),
            rec_qty: String(row.rec_qty ?? ""),
            rec_wt: String(row.rec_wt ?? ""),
            remarks: String(row.remarks ?? ""),
          };
        }),
      );
    }
    setStatus("Adjustment loaded.");
    setError("");
  }

  async function runFind() {
    const response = await bridge()?.get_stock_adjustment_entry?.({
      adjustment_date: date,
      ref_no: stkNo.trim(),
    });
    if (!response?.ok || !response.stock_adjustment) {
      setError(response?.error ?? "Not found.");
      return;
    }
    applyRecord(response.stock_adjustment);
  }

  async function openPicker(index: number, query = "") {
    const response = await bridge()?.lookup_stock_adjustment_items?.(query || lines[index]?.item_name);
    if (response?.ok && response.rows) setPicker({ index, rows: response.rows });
  }

  async function pickItem(index: number, row: Record<string, unknown>) {
    const commodityId = String(row.commodity_id ?? "");
    const hints = await bridge()?.stock_adjustment_line_hints?.(commodityId, godown);
    setLines((prev) =>
      prev.map((line, i) =>
        i === index
          ? {
              ...line,
              commodity_id: commodityId,
              item_name: String(row.item_name ?? ""),
              cur_qty: hints?.hints?.cur_qty ?? line.cur_qty,
              cur_wt: hints?.hints?.cur_wt ?? line.cur_wt,
            }
          : line,
      ),
    );
    setPicker(null);
  }

  function updateLine(index: number, patch: Partial<AdjLine>) {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const payload = {
      adjustment_id: adjustmentId || undefined,
      adjustment_date: date,
      ref_no: stkNo,
      godown,
      lines: lines
        .filter((line) => line.commodity_id)
        .map((line) => ({
          commodity_id: line.commodity_id,
          item_name: line.item_name,
          issue_qty: line.issue_qty || line.issue_wt,
          rec_qty: line.rec_qty || line.rec_wt,
          remarks: line.remarks,
        })),
    };
    const response = await bridge()?.save_stock_adjustment?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.stock_adjustment) applyRecord(response.stock_adjustment);
    setStatus("Data has been Successfully Saved");
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
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <>
      <form className="accounts-entry-screen stock-adjustment-screen" onSubmit={(event) => void save(event)}>
        <header className="accounts-entry-title">{title}</header>
        <div className="accounts-entry-toolbar centered">
          {mode === "modify" && (
            <button type="button" onClick={() => void runFind()}>
              Find F5
            </button>
          )}
          <button type="submit">Save F3</button>
          <button type="button" onClick={onExit}>
            Cancel F4
          </button>
        </div>
        <div className="stock-adj-header">
          <label>
            Date
            <input className="picker-field" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label>
            Stk.No.
            <input value={stkNo} onChange={(e) => setStkNo(e.target.value)} />
          </label>
          <label>
            Godown
            <input value={godown} onChange={(e) => setGodown(e.target.value)} />
          </label>
        </div>
        <table className="accounts-entry-grid" onKeyDown={handleGridEnter}>
          <thead>
            <tr>
              <th>#</th>
              <th>Item</th>
              <th>Cur.Qty</th>
              <th>Cur.Wt</th>
              <th>Issue Qty</th>
              <th>Issue Wt</th>
              <th>Rec. Qty</th>
              <th>Rec. Wt</th>
              <th>Remarks</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={`adj-${index}`}>
                <td>{index + 1}</td>
                <td>
                  <input
                    className="picker-field"
                    value={line.item_name}
                    onChange={(e) => updateLine(index, { item_name: e.target.value })}
                    onDoubleClick={() => void openPicker(index, line.item_name)}
                  />
                </td>
                <td>
                  <input readOnly value={line.cur_qty} />
                </td>
                <td>
                  <input readOnly value={line.cur_wt} />
                </td>
                <td>
                  <input value={line.issue_qty} onChange={(e) => updateLine(index, { issue_qty: e.target.value })} />
                </td>
                <td>
                  <input value={line.issue_wt} onChange={(e) => updateLine(index, { issue_wt: e.target.value })} />
                </td>
                <td>
                  <input value={line.rec_qty} onChange={(e) => updateLine(index, { rec_qty: e.target.value })} />
                </td>
                <td>
                  <input value={line.rec_wt} onChange={(e) => updateLine(index, { rec_wt: e.target.value })} />
                </td>
                <td>
                  <input value={line.remarks} onChange={(e) => updateLine(index, { remarks: e.target.value })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {status && <p className="accounts-entry-status">{status}</p>}
        {error && <p className="accounts-entry-error">{error}</p>}
      </form>
      {picker && (
        <div className="accounts-picker-overlay">
          <div className="accounts-picker-panel">
            <header>Select item</header>
            <ul>
              {picker.rows.map((row) => (
                <li key={String(row.commodity_id)}>
                  <button type="button" onClick={() => void pickItem(picker.index, row)}>
                    {String(row.item_name)}
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
