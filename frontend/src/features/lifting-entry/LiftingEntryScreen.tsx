import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import LiftingExpenseModal from "./LiftingExpenseModal";
import LiftingPrintModal from "./LiftingPrintModal";
import {
  ddMmYyyyToIso,
  emptyExpenseRow,
  emptyLiftingLine,
  isoToday,
  isoToDdMmYyyy,
  parseLiftingLines,
  recalcLineAmount,
  sumTotals,
  withTrailingBlankLine,
  type LiftingExpenseRow,
  type LiftingLine,
  type LiftedSummaryRow,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type LiftingApi = {
  find_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  get_lifting_entry?(args: Record<string, string>): Promise<ApiResult & { lifting_entry?: Record<string, unknown> }>;
  save_lifting_entry?(payload: Record<string, unknown>): Promise<ApiResult & { lifting_entry?: Record<string, unknown> }>;
  delete_lifting_entry?(document_id: string): Promise<ApiResult>;
  lookup_lifting_line_parties?(header_party_id: string, query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_lifting_line_items?(line_party_id: string, query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_lifting_line_rates?(line_party_id: string, commodity_id: string, ref_code?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_lifting_references?(line_party_id: string, commodity_id: string, ref_code: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lifting_lifted_qty_summary?(party_id: string, dispatch_from?: string): Promise<ApiResult & { rows?: LiftedSummaryRow[] }>;
  print_lifting_challans?(payload: Record<string, unknown>): Promise<ApiResult & { count?: number; pdf_paths?: string[] }>;
};

type PickerKind = "party_line" | "item" | "rate" | "reference" | "header_party";

type PickerState = {
  kind: PickerKind;
  lineIndex: number;
  rows: Record<string, unknown>[];
  title: string;
};

function api(): LiftingApi | undefined {
  return window.pywebview?.api as unknown as LiftingApi | undefined;
}

export default function LiftingEntryScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const title = mode === "add" ? "Lifting Entry Add" : "Lifting Entry Modify";
  const formRef = useRef<HTMLFormElement>(null);

  const [documentId, setDocumentId] = useState("");
  const [userName] = useState("USER");
  const [entryDate, setEntryDate] = useState(mode === "add" ? isoToday() : isoToDdMmYyyy(isoToday()));
  const [dispatchFrom, setDispatchFrom] = useState("");
  const [challanNo, setChallanNo] = useState("");
  const [prefix, setPrefix] = useState("");
  const [partyId, setPartyId] = useState("");
  const [partyName, setPartyName] = useState("");
  const [vehicleNo, setVehicleNo] = useState("");
  const [grNo, setGrNo] = useState("");
  const [grDate, setGrDate] = useState("");
  const [transport, setTransport] = useState("");
  const [driverName, setDriverName] = useState("");
  const [kandaWt, setKandaWt] = useState("");
  const [remarks, setRemarks] = useState("");
  const [actualWt, setActualWt] = useState("");
  const [policyNo, setPolicyNo] = useState("");
  const [poNo, setPoNo] = useState("");
  const [poDate, setPoDate] = useState("");
  const [lines, setLines] = useState<LiftingLine[]>([emptyLiftingLine()]);
  const [expenses, setExpenses] = useState<LiftingExpenseRow[]>([emptyExpenseRow()]);
  const [liftedSummary, setLiftedSummary] = useState<LiftedSummaryRow[]>([]);
  const [picker, setPicker] = useState<PickerState | null>(null);
  const [expenseOpen, setExpenseOpen] = useState(false);
  const [printOpen, setPrintOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const handleGridEnter = useGridEnterNavigation(() => {
    setLines((prev) => withTrailingBlankLine(prev));
    return false;
  });

  const expenseTotal = useMemo(
    () => expenses.reduce((sum, row) => sum + (Number(row.amount) || 0), 0),
    [expenses],
  );

  const totals = useMemo(
    () => sumTotals(lines, expenseTotal),
    [expenseTotal, lines],
  );

  const refreshLiftedSummary = useCallback(async () => {
    if (!partyId) {
      setLiftedSummary([]);
      return;
    }
    const response = await api()?.lifting_lifted_qty_summary?.(partyId, dispatchFrom);
    if (response?.ok && response.rows) setLiftedSummary(response.rows);
  }, [dispatchFrom, partyId]);

  useEffect(() => {
    void refreshLiftedSummary();
  }, [refreshLiftedSummary]);

  function applyRecord(record: Record<string, unknown>) {
    setDocumentId(String(record.document_id ?? ""));
    const iso = String(record.entry_date ?? "");
    setEntryDate(mode === "add" ? iso : isoToDdMmYyyy(iso));
    setChallanNo(String(record.challan_no ?? ""));
    setDispatchFrom(String(record.dispatch_from ?? ""));
    setPrefix(String(record.prefix ?? ""));
    setPartyId(String(record.party_id ?? ""));
    setPartyName(String(record.party_name ?? ""));
    setVehicleNo(String(record.vehicle_no ?? ""));
    setGrNo(String(record.gr_no ?? ""));
    setGrDate(String(record.gr_date ?? ""));
    setTransport(String(record.transport ?? ""));
    setDriverName(String(record.driver_name ?? ""));
    setKandaWt(String(record.kanda_wt ?? ""));
    setRemarks(String(record.remarks ?? ""));
    setActualWt(String(record.actual_wt ?? ""));
    setPolicyNo(String(record.policy_no ?? ""));
    setPoNo(String(record.po_no ?? ""));
    setPoDate(String(record.po_date ?? ""));
    setLines(parseLiftingLines(record.lines));
    const rawExpenses = record.expenses;
    if (Array.isArray(rawExpenses) && rawExpenses.length) {
      setExpenses(
        rawExpenses.map((row) => {
          const item = row as Record<string, unknown>;
          return {
            particulars: String(item.particulars ?? ""),
            exp_on: String(item.exp_on ?? "Nug"),
            extra: String(item.extra ?? "N"),
            per_pct: String(item.per_pct ?? ""),
            r_off: String(item.r_off ?? "N"),
            amount: String(item.amount ?? ""),
          };
        }),
      );
    }
    setStatus("Lifting entry loaded.");
    setError("");
  }

  async function runFind() {
    setError("");
    const isoDate = ddMmYyyyToIso(entryDate);
    const response = await api()?.get_lifting_entry?.({
      entry_date: isoDate,
      challan_no: challanNo.trim(),
      party_id: partyId,
    });
    if (!response?.ok || !response.lifting_entry) {
      setError(response?.error ?? "Lifting entry not found.");
      return;
    }
    applyRecord(response.lifting_entry);
  }

  function updateLine(index: number, patch: Partial<LiftingLine>) {
    setLines((prev) => {
      const next = prev.map((line, i) => {
        if (i !== index) return line;
        return recalcLineAmount({ ...line, ...patch });
      });
      return withTrailingBlankLine(next);
    });
  }

  async function openPicker(kind: PickerKind, lineIndex: number, query = "") {
    const bridge = api();
    if (!bridge) return;
    if (kind === "header_party") {
      const response = await bridge.find_accounts?.(query);
      if (response?.ok && response.rows) {
        setPicker({
          kind,
          lineIndex: -1,
          rows: response.rows,
          title: "AcName",
        });
      }
      return;
    }
    const line = lines[lineIndex];
    if (kind === "party_line") {
      const response = await bridge.lookup_lifting_line_parties?.(partyId, query || line.party_name);
      if (response?.ok && response.rows) {
        setPicker({ kind, lineIndex, rows: response.rows, title: "Party Name" });
      }
      return;
    }
    if (kind === "item") {
      const response = await bridge.lookup_lifting_line_items?.(line.line_party_id, query || line.item_name);
      if (response?.ok && response.rows) {
        setPicker({ kind, lineIndex, rows: response.rows, title: "Item Name" });
      }
      return;
    }
    if (kind === "rate") {
      const response = await bridge.lookup_lifting_line_rates?.(
        line.line_party_id,
        line.commodity_id,
        line.ref_code,
      );
      if (response?.ok && response.rows) {
        setPicker({ kind, lineIndex, rows: response.rows, title: "Rate" });
      }
      return;
    }
    if (kind === "reference") {
      const response = await bridge.lookup_lifting_references?.(
        line.line_party_id,
        line.commodity_id,
        line.ref_code,
      );
      if (response?.ok && response.rows) {
        setPicker({ kind, lineIndex, rows: response.rows, title: "Reference" });
      }
    }
  }

  function applyPicker(row: Record<string, unknown>) {
    if (!picker) return;
    if (picker.kind === "header_party") {
      setPartyId(String(row.party_id ?? ""));
      setPartyName(String(row.name ?? row.account_name ?? ""));
      setPicker(null);
      return;
    }
    const index = picker.lineIndex;
    if (picker.kind === "party_line") {
      updateLine(index, {
        line_party_id: String(row.party_id ?? ""),
        party_name: String(row.party_name ?? ""),
      });
    } else if (picker.kind === "item") {
      updateLine(index, {
        commodity_id: String(row.commodity_id ?? ""),
        item_name: String(row.item_name ?? ""),
        qty: String(row.qty ?? ""),
      });
    } else if (picker.kind === "rate") {
      updateLine(index, {
        rate: String(row.rate ?? ""),
        qty: String(row.qty ?? ""),
      });
    } else if (picker.kind === "reference") {
      updateLine(index, {
        reference: String(row.reference ?? ""),
        rate: String(row.rate ?? ""),
        qty: String(row.qty ?? ""),
      });
    }
    setPicker(null);
  }

  function recalculateAll() {
    setLines((prev) => prev.map((line) => recalcLineAmount(line)));
    setStatus("Recalculated.");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const isoDate = mode === "add" ? entryDate : ddMmYyyyToIso(entryDate);
    const payload = {
      document_id: documentId || undefined,
      user_name: userName,
      entry_date: isoDate,
      dispatch_from: dispatchFrom,
      challan_no: challanNo.trim(),
      prefix,
      party_id: partyId,
      party_name: partyName,
      vehicle_no: vehicleNo,
      gr_no: grNo,
      gr_date: grDate,
      transport,
      driver_name: driverName,
      kanda_wt: kandaWt,
      remarks,
      actual_wt: actualWt,
      policy_no: policyNo,
      po_no: poNo,
      po_date: poDate,
      expenses: expenses.filter((row) => row.particulars.trim()),
      lifted_summary: liftedSummary,
      totals,
      lines: lines
        .filter((line) => line.item_name.trim() || line.party_name.trim())
        .map((line) => ({ ...line })),
    };
    const response = await api()?.save_lifting_entry?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.lifting_entry) applyRecord(response.lifting_entry);
    setStatus("Data has been Successfully Saved");
    void refreshLiftedSummary();
  }

  async function confirmDelete() {
    if (!documentId) return;
    const response = await api()?.delete_lifting_entry?.(documentId);
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
        formRef.current?.requestSubmit();
      }
      if (event.key === "F4") {
        event.preventDefault();
        onExit();
      }
      if (event.key === "F5" && mode === "modify") {
        event.preventDefault();
        void runFind();
      }
      if (event.key === "F6" && mode === "modify" && documentId) {
        event.preventDefault();
        setDeleteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const totalLiftedQty = liftedSummary
    .reduce((sum, row) => sum + (Number(row.lifted_qty) || 0), 0)
    .toFixed(2);

  return (
    <>
      <form
        ref={formRef}
        className="lifting-entry-screen"
        data-lifting-entry-form
        onSubmit={(event) => void save(event)}
      >
        <header className="lifting-entry-title">{title}</header>
        <div className="lifting-entry-toolbar">
          <button type="submit">Save (F3)</button>
          <button type="button" onClick={onExit}>
            Cancel (F4)
          </button>
          {mode === "modify" && (
            <>
              <button type="button" onClick={() => void runFind()}>
                Find (F5)
              </button>
              <button disabled={!documentId} type="button" onClick={() => setDeleteOpen(true)}>
                Delete (F6)
              </button>
              <button type="button" onClick={() => setPrintOpen(true)}>
                Print
              </button>
            </>
          )}
          <button type="button" onClick={() => setExpenseOpen(true)}>
            Expense
          </button>
          <button type="button" onClick={recalculateAll}>
            Recalculate
          </button>
        </div>
        <div className="lifting-entry-header-grid">
          <div className="lifting-entry-col">
            <label>
              User Name
              <input readOnly value={userName} />
            </label>
            <label>
              Date
              <input
                type={mode === "add" ? "date" : "text"}
                placeholder={mode === "modify" ? "DD/MM/YYYY" : undefined}
                value={entryDate}
                onChange={(event) => setEntryDate(event.target.value)}
              />
            </label>
            <label>
              Party A/c
              <input
                value={partyName}
                onChange={(event) => setPartyName(event.target.value)}
                onFocus={() => void openPicker("header_party", -1, partyName)}
              />
            </label>
            <label>
              Veh.No.
              <input value={vehicleNo} onChange={(event) => setVehicleNo(event.target.value)} />
            </label>
            <div className="lifting-entry-pair">
              <label>
                Gr No.
                <input value={grNo} onChange={(event) => setGrNo(event.target.value)} />
              </label>
              <label>
                Gr Date
                <input value={grDate} onChange={(event) => setGrDate(event.target.value)} />
              </label>
            </div>
            <label>
              Transport
              <input value={transport} onChange={(event) => setTransport(event.target.value)} />
            </label>
            <div className="lifting-entry-pair">
              <label>
                Driver Name
                <input value={driverName} onChange={(event) => setDriverName(event.target.value)} />
              </label>
              <label>
                Kanda Wt.
                <input value={kandaWt} onChange={(event) => setKandaWt(event.target.value)} />
              </label>
            </div>
            <div className="lifting-entry-pair">
              <label>
                Remarks
                <input value={remarks} onChange={(event) => setRemarks(event.target.value)} />
              </label>
              <label>
                Actual Wt.
                <input value={actualWt} onChange={(event) => setActualWt(event.target.value)} />
              </label>
            </div>
            <label>
              Policy No
              <input value={policyNo} onChange={(event) => setPolicyNo(event.target.value)} />
            </label>
          </div>
          <div className="lifting-entry-col">
            <label>
              Dispatch From
              <input value={dispatchFrom} onChange={(event) => setDispatchFrom(event.target.value)} />
            </label>
            <label>
              Chln No.
              <input value={challanNo} onChange={(event) => setChallanNo(event.target.value)} />
            </label>
            <label>
              Prefix
              <input value={prefix} onChange={(event) => setPrefix(event.target.value)} />
            </label>
            <div className="lifting-entry-pair">
              <label>
                PO No.
                <input value={poNo} onChange={(event) => setPoNo(event.target.value)} />
              </label>
              <label>
                PO Date
                <input value={poDate} onChange={(event) => setPoDate(event.target.value)} />
              </label>
            </div>
            <div className="lifting-entry-totals">
              <span>Total Qty.: {totals.total_qty}</span>
              <span>Total Weight: {totals.total_weight}</span>
              <span>Total Amount: {totals.total_amount}</span>
              <span>Total Expense: {totals.total_expense}</span>
              <span>Total (Amt + Exp): {totals.total_amt_exp}</span>
            </div>
          </div>
          <div className="lifting-entry-summary-panel">
            <table>
              <thead>
                <tr>
                  <th>Item/Crop</th>
                  <th>Lifted Qty</th>
                </tr>
              </thead>
              <tbody>
                {liftedSummary.map((row) => (
                  <tr key={row.item_name}>
                    <td>{row.item_name}</td>
                    <td>{row.lifted_qty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="lifting-entry-summary-total">Total Lifted Qty : {totalLiftedQty}</p>
          </div>
        </div>
        <div className="lifting-entry-grid-wrap" onKeyDown={handleGridEnter}>
          <table className="lifting-entry-grid">
            <thead>
              <tr>
                <th>#</th>
                <th>Party Name</th>
                <th>Remarks</th>
                <th>Item Name</th>
                <th>Unit</th>
                <th>Rate</th>
                <th>Ref. Code</th>
                <th>Reference</th>
                <th>Qty</th>
                <th>Weight</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={`line-${index}`} data-grid-row>
                  <td>{index + 1}</td>
                  <td>
                    <input
                      value={line.party_name}
                      onChange={(event) => updateLine(index, { party_name: event.target.value })}
                      onFocus={() => void openPicker("party_line", index)}
                    />
                  </td>
                  <td>
                    <input
                      value={line.remarks}
                      onChange={(event) => updateLine(index, { remarks: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.item_name}
                      onChange={(event) => updateLine(index, { item_name: event.target.value })}
                      onFocus={() => void openPicker("item", index)}
                    />
                  </td>
                  <td>
                    <input
                      value={line.unit}
                      onChange={(event) => updateLine(index, { unit: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.rate}
                      onChange={(event) => updateLine(index, { rate: event.target.value })}
                      onFocus={() => void openPicker("rate", index)}
                    />
                  </td>
                  <td>
                    <input
                      value={line.ref_code}
                      onChange={(event) => updateLine(index, { ref_code: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.reference}
                      onChange={(event) => updateLine(index, { reference: event.target.value })}
                      onFocus={() => void openPicker("reference", index)}
                    />
                  </td>
                  <td>
                    <input
                      value={line.qty}
                      onChange={(event) => updateLine(index, { qty: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.weight}
                      onChange={(event) => updateLine(index, { weight: event.target.value })}
                    />
                  </td>
                  <td>
                    <input readOnly value={line.amount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(status || error) && (
          <p className={`lifting-entry-status${error ? " lifting-entry-error" : ""}`}>{error || status}</p>
        )}
      </form>
      {picker && (
        <div className="lifting-picker" role="listbox">
          <div className="lifting-picker-header">{picker.title}</div>
          <ul>
            {picker.rows.map((row, index) => (
              <li key={`pick-${index}`}>
                <button type="button" onClick={() => applyPicker(row)}>
                  {picker.kind === "header_party"
                    ? `${String(row.name ?? "")} · ${String(row.city ?? "")}`
                    : picker.kind === "party_line"
                      ? `${String(row.party_name ?? "")} · ${String(row.qty ?? "")} · ${String(row.city ?? "")}`
                      : picker.kind === "item"
                        ? `${String(row.item_name ?? "")} · ${String(row.qty ?? "")}`
                        : picker.kind === "rate"
                          ? `${String(row.rate ?? "")} · ${String(row.qty ?? "")}`
                          : `${String(row.reference ?? "")} · ${String(row.qty ?? "")}`}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <LiftingExpenseModal
        open={expenseOpen}
        onAmt={totals.total_amount}
        onClose={() => setExpenseOpen(false)}
        onQty={totals.total_qty}
        onSave={setExpenses}
        onWt={totals.total_weight}
        rows={expenses}
        title={`Lifting Expense (${partyName || "Party"})`}
      />
      <LiftingPrintModal
        defaultAccount={partyName}
        open={printOpen}
        onClose={() => setPrintOpen(false)}
        onPrint={async (payload) => {
          const response = await api()?.print_lifting_challans?.(payload);
          if (!response?.ok) return { error: response?.error ?? "Print failed" };
          return { count: response.count, pdf_paths: response.pdf_paths };
        }}
      />
      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={`Challan ${challanNo}`}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
