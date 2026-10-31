import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import LiftingExpenseModal from "../lifting-entry/LiftingExpenseModal";
import { emptyExpenseRow } from "../lifting-entry/constants";
import {
  buildRateSummary,
  ddMmYyyyToIso,
  emptyGstLine,
  isoToday,
  isoToDdMmYyyy,
  parseGstLines,
  recalcGstLine,
  sumGstHeaderTotals,
  weekdayLabel,
  withTrailingBlankLine,
  type GstLine,
  type LiftingExpenseRow,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type GstApi = {
  get_gst_purchase_entry?(args: Record<string, string>): Promise<
    ApiResult & { gst_purchase_entry?: Record<string, unknown> }
  >;
  save_gst_purchase_entry?(payload: Record<string, unknown>): Promise<
    ApiResult & { gst_purchase_entry?: Record<string, unknown> }
  >;
  delete_gst_purchase_entry?(document_id: string): Promise<ApiResult>;
  lookup_gst_parties?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_gst_items?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_gst_purchase_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  next_gst_entry_number?(): Promise<ApiResult & { document_number?: string }>;
};

type PickerKind = "party" | "item" | "purchase_ac";
type SideTab = "rates" | "expens";

function api(): GstApi | undefined {
  return window.pywebview?.api as unknown as GstApi | undefined;
}

export default function GstPurchaseEntryScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const title = mode === "add" ? "Normal GST Purchase Add" : "Normal GST Purchase Modify";
  const formRef = useRef<HTMLFormElement>(null);

  const [documentId, setDocumentId] = useState("");
  const [documentNumber, setDocumentNumber] = useState("");
  const [userName] = useState("USER");
  const [entryDate, setEntryDate] = useState(mode === "add" ? isoToday() : isoToDdMmYyyy(isoToday()));
  const [cashCredit, setCashCredit] = useState("R");
  const [lstCst, setLstCst] = useState("L");
  const [revCharges, setRevCharges] = useState("N");
  const [partyId, setPartyId] = useState("");
  const [partyName, setPartyName] = useState("");
  const [broker, setBroker] = useState("");
  const [billNo, setBillNo] = useState("");
  const [billDate, setBillDate] = useState("");
  const [orderNo, setOrderNo] = useState("");
  const [orderDate, setOrderDate] = useState("");
  const [dispatch, setDispatch] = useState("");
  const [transport, setTransport] = useState("");
  const [freight, setFreight] = useState("");
  const [vehNo, setVehNo] = useState("");
  const [grNo, setGrNo] = useState("");
  const [grDate, setGrDate] = useState("");
  const [partyGstType, setPartyGstType] = useState("R");
  const [inputClaim, setInputClaim] = useState("Y");
  const [dueDays, setDueDays] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [roundOff, setRoundOff] = useState("A");
  const [tcsPct, setTcsPct] = useState("");
  const [tcsOn, setTcsOn] = useState("");
  const [tcsAmt, setTcsAmt] = useState("");
  const [tdsOn, setTdsOn] = useState("Net");
  const [tdsPct, setTdsPct] = useState("");
  const [tdsAmt, setTdsAmt] = useState("");
  const [tdsAdj, setTdsAdj] = useState("");
  const [addAny, setAddAny] = useState("");
  const [lessAny, setLessAny] = useState("");
  const [unloadDate, setUnloadDate] = useState("");
  const [inputClaimDt, setInputClaimDt] = useState("");
  const [ewayNo, setEwayNo] = useState("");
  const [sMitti, setSMitti] = useState("");
  const [lForm, setLForm] = useState("N");
  const [remarks, setRemarks] = useState("");
  const [lines, setLines] = useState<GstLine[]>([emptyGstLine()]);
  const [expenses, setExpenses] = useState<LiftingExpenseRow[]>([emptyExpenseRow()]);
  const [sideTab, setSideTab] = useState<SideTab>("rates");
  const [expenseOpen, setExpenseOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [picker, setPicker] = useState<{ kind: PickerKind; lineIndex: number; rows: Record<string, unknown>[] } | null>(
    null,
  );
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const headerTotals = useMemo(() => sumGstHeaderTotals(lines), [lines]);
  const rateRows = useMemo(() => buildRateSummary(lines), [lines]);
  const weekday = useMemo(
    () => weekdayLabel(mode === "add" ? entryDate : ddMmYyyyToIso(entryDate)),
    [entryDate, mode],
  );

  const handleGridEnter = useGridEnterNavigation(() => {
    setLines((prev) => withTrailingBlankLine(prev));
    return false;
  });

  useEffect(() => {
    if (mode !== "add") return;
    void api()?.next_gst_entry_number?.().then((response) => {
      if (response?.ok && response.document_number) setDocumentNumber(response.document_number);
    });
  }, [mode]);

  function applyRecord(record: Record<string, unknown>) {
    setDocumentId(String(record.document_id ?? ""));
    setDocumentNumber(String(record.document_number ?? ""));
    const iso = String(record.entry_date ?? "");
    setEntryDate(mode === "add" ? iso : isoToDdMmYyyy(iso));
    setCashCredit(String(record.cash_credit ?? "R"));
    setLstCst(String(record.lst_cst ?? "L"));
    setRevCharges(String(record.rev_charges ?? "N"));
    setPartyId(String(record.party_id ?? ""));
    setPartyName(String(record.party_name ?? ""));
    setBroker(String(record.broker ?? ""));
    setBillNo(String(record.bill_no ?? ""));
    setBillDate(String(record.bill_date ?? ""));
    setOrderNo(String(record.order_no ?? ""));
    setOrderDate(String(record.order_date ?? ""));
    setDispatch(String(record.dispatch ?? ""));
    setTransport(String(record.transport ?? ""));
    setFreight(String(record.freight ?? ""));
    setVehNo(String(record.veh_no ?? ""));
    setGrNo(String(record.gr_no ?? ""));
    setGrDate(String(record.gr_date ?? ""));
    setPartyGstType(String(record.party_gst_type ?? "R"));
    setInputClaim(String(record.input_claim ?? "Y"));
    setDueDays(String(record.due_days ?? ""));
    setDueDate(String(record.due_date ?? ""));
    setRoundOff(String(record.round_off ?? "A"));
    setTcsPct(String(record.tcs_pct ?? ""));
    setTcsOn(String(record.tcs_on ?? ""));
    setTcsAmt(String(record.tcs_amt ?? ""));
    setTdsOn(String(record.tds_on ?? "Net"));
    setTdsPct(String(record.tds_pct ?? ""));
    setTdsAmt(String(record.tds_amt ?? ""));
    setTdsAdj(String(record.tds_adj ?? ""));
    setAddAny(String(record.add_any ?? ""));
    setLessAny(String(record.less_any ?? ""));
    setUnloadDate(String(record.unload_date ?? ""));
    setInputClaimDt(String(record.input_claim_dt ?? ""));
    setEwayNo(String(record.eway_no ?? ""));
    setSMitti(String(record.s_mitti ?? ""));
    setLForm(String(record.l_form ?? "N"));
    setRemarks(String(record.remarks ?? ""));
    setLines(parseGstLines(record.lines));
    setStatus("GST purchase loaded.");
    setError("");
  }

  async function runFind() {
    const response = await api()?.get_gst_purchase_entry?.({
      entry_date: ddMmYyyyToIso(entryDate),
      party_id: partyId,
      bill_no: billNo.trim(),
    });
    if (!response?.ok || !response.gst_purchase_entry) {
      setError(response?.error ?? "Entry not found.");
      return;
    }
    applyRecord(response.gst_purchase_entry);
  }

  function updateLine(index: number, patch: Partial<GstLine>) {
    setLines((prev) => {
      const next = prev.map((line, i) => (i === index ? recalcGstLine({ ...line, ...patch }) : line));
      return withTrailingBlankLine(next);
    });
  }

  async function openPicker(kind: PickerKind, lineIndex: number, query = "") {
    const bridge = api();
    if (!bridge) return;
    if (kind === "party") {
      const response = await bridge.lookup_gst_parties?.(query || partyName);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex: -1, rows: response.rows });
      return;
    }
    const line = lines[lineIndex];
    if (kind === "item") {
      const response = await bridge.lookup_gst_items?.(query || line.item_name);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
      return;
    }
    if (kind === "purchase_ac") {
      const response = await bridge.lookup_gst_purchase_accounts?.(query || line.purchase_ac);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
    }
  }

  function applyPicker(row: Record<string, unknown>) {
    if (!picker) return;
    if (picker.kind === "party") {
      setPartyId(String(row.party_id ?? ""));
      setPartyName(String(row.name ?? ""));
      setPicker(null);
      return;
    }
    const index = picker.lineIndex;
    if (picker.kind === "item") {
      updateLine(index, {
        commodity_id: String(row.commodity_id ?? ""),
        item_name: String(row.item_name ?? ""),
        item_desc: String(row.item_name ?? ""),
        hsn_code: String(row.hsn_code ?? ""),
        unit: String(row.unit ?? "Qtls"),
      });
    } else if (picker.kind === "purchase_ac") {
      updateLine(index, {
        purchase_ac_id: String(row.account_id ?? ""),
        purchase_ac: String(row.account_name ?? ""),
      });
    }
    setPicker(null);
  }

  function recalculateAll() {
    setLines((prev) => prev.map((line) => recalcGstLine(line)));
    setStatus("Recalculated.");
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const isoDate = mode === "add" ? entryDate : ddMmYyyyToIso(entryDate);
    const payload: Record<string, unknown> = {
      document_id: documentId || undefined,
      document_number: documentNumber,
      entry_date: isoDate,
      user_name: userName,
      cash_credit: cashCredit,
      lst_cst: lstCst,
      rev_charges: revCharges,
      party_id: partyId,
      party_name: partyName,
      broker,
      bill_no: billNo,
      bill_date: billDate,
      order_no: orderNo,
      order_date: orderDate,
      dispatch,
      transport,
      freight,
      veh_no: vehNo,
      gr_no: grNo,
      gr_date: grDate,
      party_gst_type: partyGstType,
      input_claim: inputClaim,
      due_days: dueDays,
      due_date: dueDate,
      round_off: roundOff,
      tcs_pct: tcsPct,
      tcs_on: tcsOn,
      tcs_amt: tcsAmt,
      tds_on: tdsOn,
      tds_pct: tdsPct,
      tds_amt: tdsAmt,
      tds_adj: tdsAdj,
      add_any: addAny,
      less_any: lessAny,
      unload_date: unloadDate,
      input_claim_dt: inputClaimDt,
      eway_no: ewayNo,
      s_mitti: sMitti,
      l_form: lForm,
      remarks,
      gst_amt: headerTotals.gst_amt,
      bill_amt: headerTotals.bill_amt,
      expenses,
      rate_rows: rateRows,
      lines: lines.filter((line) => line.item_name.trim()),
    };
    const response = await api()?.save_gst_purchase_entry?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.gst_purchase_entry) applyRecord(response.gst_purchase_entry);
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
      if (event.key === "F6" && mode === "modify" && documentId) {
        event.preventDefault();
        setDeleteOpen(true);
      }
      if (event.key === "F11") {
        const active = document.activeElement?.closest<HTMLElement>("[data-grid-row]");
        const index = active?.dataset.lineIndex;
        if (index !== undefined) void openPicker("purchase_ac", Number(index));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  async function confirmDelete() {
    if (!documentId) return;
    const response = await api()?.delete_gst_purchase_entry?.(documentId);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    onExit();
  }

  return (
    <>
      <form ref={formRef} className="gst-purchase-screen" onSubmit={(event) => void save(event)}>
        <header className="gst-purchase-title">{title}</header>
        <div className="gst-purchase-toolbar">
          <span className="gst-purchase-weekday">{weekday}</span>
          <span className="gst-purchase-user">User: {userName}</span>
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
            </>
          )}
          <button type="button" onClick={() => setExpenseOpen(true)}>
            Expenses
          </button>
          <button className="gst-purchase-recalc" type="button" onClick={recalculateAll}>
            Recalculate
          </button>
        </div>
        <div className="gst-purchase-header">
          <div className="gst-purchase-fields">
            <label>
              Date
              <input
                type={mode === "add" ? "date" : "text"}
                value={entryDate}
                onChange={(event) => setEntryDate(event.target.value)}
              />
            </label>
            <label>
              Cash/Credit
              <select value={cashCredit} onChange={(event) => setCashCredit(event.target.value)}>
                <option value="R">R</option>
                <option value="C">C</option>
              </select>
            </label>
            <label>
              Lst/Cst
              <select value={lstCst} onChange={(event) => setLstCst(event.target.value)}>
                <option value="L">L</option>
                <option value="C">C</option>
              </select>
            </label>
            <label>
              Rev. Charges
              <select value={revCharges} onChange={(event) => setRevCharges(event.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
            <label className="wide">
              Party A/c
              <input
                value={partyName}
                onChange={(event) => setPartyName(event.target.value)}
                onFocus={() => void openPicker("party", -1, partyName)}
              />
            </label>
            <label>
              Broker
              <input value={broker} onChange={(event) => setBroker(event.target.value)} />
            </label>
            <label>
              Bill No.
              <input value={billNo} onChange={(event) => setBillNo(event.target.value)} />
            </label>
            <label>
              Bill Date
              <input value={billDate} onChange={(event) => setBillDate(event.target.value)} />
            </label>
            <label>
              Order No.
              <input value={orderNo} onChange={(event) => setOrderNo(event.target.value)} />
            </label>
            <label>
              Order Date
              <input value={orderDate} onChange={(event) => setOrderDate(event.target.value)} />
            </label>
            <label>
              Dispatch
              <input value={dispatch} onChange={(event) => setDispatch(event.target.value)} />
            </label>
            <label>
              Transport
              <input value={transport} onChange={(event) => setTransport(event.target.value)} />
            </label>
            <label>
              Freight
              <input value={freight} onChange={(event) => setFreight(event.target.value)} />
            </label>
            <label>
              Veh No.
              <input value={vehNo} onChange={(event) => setVehNo(event.target.value)} />
            </label>
            <label>
              Gr No.
              <input value={grNo} onChange={(event) => setGrNo(event.target.value)} />
            </label>
            <label>
              Gr Date
              <input value={grDate} onChange={(event) => setGrDate(event.target.value)} />
            </label>
            <label>
              Party GST Type
              <select value={partyGstType} onChange={(event) => setPartyGstType(event.target.value)}>
                <option value="R">R</option>
                <option value="U">U</option>
              </select>
            </label>
            <label>
              Input Claim (Y/N)
              <select value={inputClaim} onChange={(event) => setInputClaim(event.target.value)}>
                <option value="Y">Y</option>
                <option value="N">N</option>
              </select>
            </label>
            <label>
              Due Days
              <input value={dueDays} onChange={(event) => setDueDays(event.target.value)} />
            </label>
            <label>
              Due Date
              <input value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            </label>
            <label>
              Round Off
              <select value={roundOff} onChange={(event) => setRoundOff(event.target.value)}>
                <option value="A">A</option>
                <option value="N">N</option>
              </select>
            </label>
            <label>
              TCS %
              <input value={tcsPct} onChange={(event) => setTcsPct(event.target.value)} />
            </label>
            <label>
              TCS On
              <input value={tcsOn} onChange={(event) => setTcsOn(event.target.value)} />
            </label>
            <label>
              TCS Amt
              <input value={tcsAmt} onChange={(event) => setTcsAmt(event.target.value)} />
            </label>
            <label>
              TDS On
              <select value={tdsOn} onChange={(event) => setTdsOn(event.target.value)}>
                <option value="Net">Net</option>
                <option value="Gross">Gross</option>
              </select>
            </label>
            <label>
              TDS %
              <input value={tdsPct} onChange={(event) => setTdsPct(event.target.value)} />
            </label>
            <label>
              TDS Amt
              <input value={tdsAmt} onChange={(event) => setTdsAmt(event.target.value)} />
            </label>
            <label>
              TDS Adj.
              <input value={tdsAdj} onChange={(event) => setTdsAdj(event.target.value)} />
            </label>
            <label>
              GST Amt.
              <input readOnly value={headerTotals.gst_amt} />
            </label>
            <label>
              Bill Amt.
              <input readOnly className="gst-bill-amt" value={headerTotals.bill_amt} />
            </label>
            <label>
              E-Way No.
              <input value={ewayNo} onChange={(event) => setEwayNo(event.target.value)} />
            </label>
            <label>
              L Form (Y/N)
              <select value={lForm} onChange={(event) => setLForm(event.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
            <label className="wide">
              Remarks
              <input value={remarks} onChange={(event) => setRemarks(event.target.value)} />
            </label>
          </div>
          <div className="gst-purchase-side">
            <div className="gst-purchase-side-tabs">
              <button
                className={sideTab === "rates" ? "active rates" : "rates"}
                type="button"
                onClick={() => setSideTab("rates")}
              >
                Rates
              </button>
              <button
                className={sideTab === "expens" ? "active expens" : "expens"}
                type="button"
                onClick={() => {
                  setSideTab("expens");
                  setExpenseOpen(true);
                }}
              >
                Expens
              </button>
            </div>
            {sideTab === "rates" && (
              <table className="gst-rate-table">
                <thead>
                  <tr>
                    <th>Rate</th>
                    <th>GST ON</th>
                    <th>CGST</th>
                    <th>SGST</th>
                    <th>IGST</th>
                    <th>Total GST</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {rateRows.map((row) => (
                    <tr key={`${row.rate}-${row.gst_on}`}>
                      <td>{row.rate}</td>
                      <td>{row.gst_on}</td>
                      <td>{row.cgst}</td>
                      <td>{row.sgst}</td>
                      <td>{row.igst}</td>
                      <td>{row.total_gst}</td>
                      <td>{row.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        <div className="gst-purchase-grid-wrap" onKeyDown={handleGridEnter}>
          <table className="gst-purchase-grid">
            <thead>
              <tr>
                <th>#</th>
                <th>Item</th>
                <th>Item Desc</th>
                <th>Purchase A/c (F11)</th>
                <th>Unit</th>
                <th>Sauda No</th>
                <th>Qty</th>
                <th>Bharti</th>
                <th>Gross Wt.</th>
                <th>Tare</th>
                <th>+/- Wt.</th>
                <th>Net Wt.</th>
                <th>N/W</th>
                <th>Rate</th>
                <th>Amount</th>
                <th>HSN</th>
                <th>Gst Adj.</th>
                <th>Gst Amt</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={`gst-${index}`} data-grid-row data-line-index={index}>
                  <td>{index + 1}</td>
                  <td>
                    <input
                      value={line.item_name}
                      onChange={(event) => updateLine(index, { item_name: event.target.value })}
                      onFocus={() => void openPicker("item", index)}
                    />
                  </td>
                  <td>
                    <input
                      value={line.item_desc}
                      onChange={(event) => updateLine(index, { item_desc: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.purchase_ac}
                      onChange={(event) => updateLine(index, { purchase_ac: event.target.value })}
                      onFocus={() => void openPicker("purchase_ac", index)}
                    />
                  </td>
                  <td>
                    <input value={line.unit} onChange={(event) => updateLine(index, { unit: event.target.value })} />
                  </td>
                  <td>
                    <input
                      value={line.sauda_no}
                      onChange={(event) => updateLine(index, { sauda_no: event.target.value })}
                    />
                  </td>
                  <td>
                    <input value={line.qty} onChange={(event) => updateLine(index, { qty: event.target.value })} />
                  </td>
                  <td>
                    <input
                      value={line.bharti}
                      onChange={(event) => updateLine(index, { bharti: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.gross_wt}
                      onChange={(event) => updateLine(index, { gross_wt: event.target.value })}
                    />
                  </td>
                  <td>
                    <input value={line.tare} onChange={(event) => updateLine(index, { tare: event.target.value })} />
                  </td>
                  <td>
                    <input
                      value={line.adj_wt}
                      onChange={(event) => updateLine(index, { adj_wt: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.net_wt}
                      onChange={(event) => updateLine(index, { net_wt: event.target.value })}
                    />
                  </td>
                  <td>
                    <select value={line.nw} onChange={(event) => updateLine(index, { nw: event.target.value })}>
                      <option value="N">N</option>
                      <option value="Y">Y</option>
                    </select>
                  </td>
                  <td>
                    <input value={line.rate} onChange={(event) => updateLine(index, { rate: event.target.value })} />
                  </td>
                  <td>
                    <input readOnly value={line.amount} />
                  </td>
                  <td>
                    <input
                      value={line.hsn_code}
                      onChange={(event) => updateLine(index, { hsn_code: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.gst_adj}
                      onChange={(event) => updateLine(index, { gst_adj: event.target.value })}
                    />
                  </td>
                  <td>
                    <input readOnly value={line.gst_amt} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(status || error) && (
          <p className={`gst-purchase-status${error ? " gst-purchase-error" : ""}`}>{error || status}</p>
        )}
      </form>
      {picker && (
        <div className="gst-picker" role="listbox">
          <ul>
            {picker.rows.map((row, index) => (
              <li key={`pick-${index}`}>
                <button type="button" onClick={() => applyPicker(row)}>
                  {picker.kind === "party"
                    ? String(row.name ?? "")
                    : picker.kind === "item"
                      ? String(row.item_name ?? "")
                      : String(row.account_name ?? "")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <LiftingExpenseModal
        open={expenseOpen}
        onAmt={headerTotals.taxable}
        onClose={() => setExpenseOpen(false)}
        onQty="0"
        onSave={setExpenses}
        onWt="0"
        rows={expenses}
        title={`GST Purchase Expenses (${partyName || "Party"})`}
      />
      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={billNo || documentNumber}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
