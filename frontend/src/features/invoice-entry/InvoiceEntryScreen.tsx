import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import LiftingExpenseModal from "../lifting-entry/LiftingExpenseModal";
import { emptyExpenseRow } from "../lifting-entry/constants";
import {
  buildLineSideRows,
  buildRateSummary,
  ddMmYyyyToIso,
  emptyInvoiceLine,
  emptySideRow,
  isoToday,
  isoToDdMmYyyy,
  parseInvoiceLines,
  recalcInvoiceLine,
  sumInvoiceHeaderTotals,
  weekdayLabel,
  withTrailingBlankLine,
  type InvoiceLine,
  type LiftingExpenseRow,
  type SideCategoryRow,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type InvoiceApi = {
  get_invoice_entry?(args: Record<string, string>): Promise<ApiResult & { invoice_entry?: Record<string, unknown> }>;
  save_invoice_entry?(payload: Record<string, unknown>): Promise<ApiResult & { invoice_entry?: Record<string, unknown> }>;
  delete_invoice_entry?(document_id: string): Promise<ApiResult>;
  lookup_invoice_parties?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_invoice_items?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_invoice_sale_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_invoice_brokers?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  next_invoice_entry_number?(): Promise<ApiResult & { document_number?: string }>;
  print_document?(document_id: string): Promise<ApiResult>;
};

type PickerKind = "party" | "item" | "sale_ac" | "broker";
type SideCatTab = "rates" | "expense" | "bardana" | "ship" | "other";

function api(): InvoiceApi | undefined {
  return window.pywebview?.api as unknown as InvoiceApi | undefined;
}

function parseSideRows(raw: unknown): SideCategoryRow[] {
  if (!Array.isArray(raw) || !raw.length) return [emptySideRow()];
  return [...raw.map((row) => {
    const item = row as Record<string, unknown>;
    return {
      item_name: String(item.item_name ?? ""),
      nugs: String(item.nugs ?? ""),
      weight: String(item.weight ?? ""),
      amount: String(item.amount ?? ""),
    };
  }), emptySideRow()];
}

export default function InvoiceEntryScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const title = mode === "add" ? "Invoice Add" : "Invoice Modify";
  const formRef = useRef<HTMLFormElement>(null);

  const [documentId, setDocumentId] = useState("");
  const [bookNo, setBookNo] = useState("");
  const [billNo, setBillNo] = useState("");
  const [userName] = useState("USER");
  const [entryDate, setEntryDate] = useState(mode === "add" ? isoToday() : isoToDdMmYyyy(isoToday()));
  const [cashCredit, setCashCredit] = useState("Credit");
  const [localCentral, setLocalCentral] = useState("Local");
  const [partyId, setPartyId] = useState("");
  const [partyName, setPartyName] = useState("");
  const [dispatch, setDispatch] = useState("");
  const [dueDays, setDueDays] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [brokerId, setBrokerId] = useState("");
  const [brokerName, setBrokerName] = useState("");
  const [consignee, setConsignee] = useState("");
  const [grNo, setGrNo] = useState("");
  const [grDate, setGrDate] = useState("");
  const [freight, setFreight] = useState("");
  const [transport, setTransport] = useState("");
  const [vehNo, setVehNo] = useState("");
  const [ewayNo, setEwayNo] = useState("");
  const [driverName, setDriverName] = useState("");
  const [orderNo, setOrderNo] = useState("");
  const [policyNo, setPolicyNo] = useState("");
  const [dispatchAc, setDispatchAc] = useState("");
  const [remarks, setRemarks] = useState("");
  const [saudaMitti, setSaudaMitti] = useState("");
  const [consigneeFlag, setConsigneeFlag] = useState("N");
  const [chForm, setChForm] = useState("N");
  const [roundOff, setRoundOff] = useState("N");
  const [gstType, setGstType] = useState("U");
  const [scrapBill, setScrapBill] = useState("N");
  const [tcsRoundOff, setTcsRoundOff] = useState("Y");
  const [tcsPct, setTcsPct] = useState("");
  const [tcsOn, setTcsOn] = useState("");
  const [tcsAmt, setTcsAmt] = useState("");
  const [rOffAmt, setROffAmt] = useState("");
  const [qFormNo, setQFormNo] = useState("");
  const [lines, setLines] = useState<InvoiceLine[]>([emptyInvoiceLine()]);
  const [expenses, setExpenses] = useState<LiftingExpenseRow[]>([emptyExpenseRow()]);
  const [bardanaRows, setBardanaRows] = useState<SideCategoryRow[]>([emptySideRow()]);
  const [shipRows, setShipRows] = useState<SideCategoryRow[]>([emptySideRow()]);
  const [otherRows, setOtherRows] = useState<SideCategoryRow[]>([emptySideRow()]);
  const [sideCatTab, setSideCatTab] = useState<SideCatTab>("rates");
  const [expenseOpen, setExpenseOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [picker, setPicker] = useState<{ kind: PickerKind; lineIndex: number; rows: Record<string, unknown>[] } | null>(
    null,
  );
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const rateRows = useMemo(() => buildRateSummary(lines), [lines]);
  const sideLineRows = useMemo(() => buildLineSideRows(lines), [lines]);
  const headerTotals = useMemo(() => sumInvoiceHeaderTotals(lines, rOffAmt), [lines, rOffAmt]);
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
    void api()?.next_invoice_entry_number?.().then((response) => {
      if (response?.ok && response.document_number) setBookNo(response.document_number);
    });
  }, [mode]);

  function applyRecord(record: Record<string, unknown>) {
    setDocumentId(String(record.document_id ?? ""));
    setBookNo(String(record.book_no ?? record.document_number ?? ""));
    setBillNo(String(record.bill_no ?? ""));
    const iso = String(record.entry_date ?? "");
    setEntryDate(mode === "add" ? iso : isoToDdMmYyyy(iso));
    setCashCredit(String(record.cash_credit ?? "Credit"));
    setLocalCentral(String(record.local_central ?? "Local"));
    setPartyId(String(record.party_id ?? ""));
    setPartyName(String(record.party_name ?? ""));
    setDispatch(String(record.dispatch ?? ""));
    setDueDays(String(record.due_days ?? ""));
    setDueDate(String(record.due_date ?? ""));
    setBrokerId(String(record.broker_id ?? ""));
    setBrokerName(String(record.broker_name ?? record.broker ?? ""));
    setConsignee(String(record.consignee ?? ""));
    setGrNo(String(record.gr_no ?? ""));
    setGrDate(String(record.gr_date ?? ""));
    setFreight(String(record.freight ?? ""));
    setTransport(String(record.transport ?? ""));
    setVehNo(String(record.veh_no ?? ""));
    setEwayNo(String(record.eway_no ?? ""));
    setDriverName(String(record.driver_name ?? ""));
    setOrderNo(String(record.order_no ?? ""));
    setPolicyNo(String(record.policy_no ?? ""));
    setDispatchAc(String(record.dispatch_ac ?? ""));
    setRemarks(String(record.remarks ?? ""));
    setSaudaMitti(String(record.sauda_mitti ?? ""));
    setConsigneeFlag(String(record.consignee_flag ?? "N"));
    setChForm(String(record.ch_form ?? "N"));
    setRoundOff(String(record.round_off ?? "N"));
    setGstType(String(record.gst_type ?? "U"));
    setScrapBill(String(record.scrap_bill ?? "N"));
    setTcsRoundOff(String(record.tcs_round_off ?? "Y"));
    setTcsPct(String(record.tcs_pct ?? ""));
    setTcsOn(String(record.tcs_on ?? ""));
    setTcsAmt(String(record.tcs_amt ?? ""));
    setROffAmt(String(record.r_off_amt ?? ""));
    setQFormNo(String(record.q_form_no ?? ""));
    setLines(parseInvoiceLines(record.lines));
    setBardanaRows(parseSideRows(record.bardana_rows));
    setShipRows(parseSideRows(record.ship_rows));
    setOtherRows(parseSideRows(record.other_rows));
    setStatus("Invoice loaded.");
    setError("");
  }

  async function runFind() {
    const response = await api()?.get_invoice_entry?.({
      entry_date: ddMmYyyyToIso(entryDate),
      party_id: partyId,
      bill_no: billNo.trim(),
      book_no: bookNo.trim(),
    });
    if (!response?.ok || !response.invoice_entry) {
      setError(response?.error ?? "Entry not found.");
      return;
    }
    applyRecord(response.invoice_entry);
  }

  function updateLine(index: number, patch: Partial<InvoiceLine>) {
    setLines((prev) => {
      const next = prev.map((line, i) => (i === index ? recalcInvoiceLine({ ...line, ...patch }) : line));
      return withTrailingBlankLine(next);
    });
  }

  async function openPicker(kind: PickerKind, lineIndex: number, query = "") {
    const bridge = api();
    if (!bridge) return;
    if (kind === "party") {
      const response = await bridge.lookup_invoice_parties?.(query || partyName);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex: -1, rows: response.rows });
      return;
    }
    if (kind === "broker") {
      const response = await bridge.lookup_invoice_brokers?.(query || brokerName);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex: -1, rows: response.rows });
      return;
    }
    const line = lines[lineIndex];
    if (kind === "item") {
      const response = await bridge.lookup_invoice_items?.(query || line.item_name);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
      return;
    }
    if (kind === "sale_ac") {
      const response = await bridge.lookup_invoice_sale_accounts?.(query || line.sale_ac);
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
    if (picker.kind === "broker") {
      setBrokerId(String(row.broker_id ?? row.party_id ?? ""));
      setBrokerName(String(row.broker_name ?? row.name ?? ""));
      setPicker(null);
      return;
    }
    const index = picker.lineIndex;
    if (picker.kind === "item") {
      updateLine(index, {
        commodity_id: String(row.commodity_id ?? ""),
        item_name: String(row.item_name ?? ""),
        item_desc: String(row.item_name ?? ""),
        unit: String(row.unit ?? "Qtls"),
      });
    } else if (picker.kind === "sale_ac") {
      updateLine(index, {
        sale_ac_id: String(row.account_id ?? ""),
        sale_ac: String(row.account_name ?? ""),
      });
    }
    setPicker(null);
  }

  function recalculateAll() {
    setLines((prev) => prev.map((line) => recalcInvoiceLine(line)));
    setStatus("Recalculated.");
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const isoDate = mode === "add" ? entryDate : ddMmYyyyToIso(entryDate);
    const payload: Record<string, unknown> = {
      document_id: documentId || undefined,
      document_number: bookNo,
      book_no: bookNo,
      bill_no: billNo,
      entry_date: isoDate,
      user_name: userName,
      cash_credit: cashCredit,
      local_central: localCentral,
      party_id: partyId,
      party_name: partyName,
      dispatch,
      due_days: dueDays,
      due_date: dueDate,
      broker_id: brokerId,
      broker_name: brokerName,
      consignee,
      gr_no: grNo,
      gr_date: grDate,
      freight,
      transport,
      veh_no: vehNo,
      eway_no: ewayNo,
      driver_name: driverName,
      order_no: orderNo,
      policy_no: policyNo,
      dispatch_ac: dispatchAc,
      remarks,
      sauda_mitti: saudaMitti,
      consignee_flag: consigneeFlag,
      ch_form: chForm,
      round_off: roundOff,
      gst_type: gstType,
      scrap_bill: scrapBill,
      tcs_round_off: tcsRoundOff,
      tcs_pct: tcsPct,
      tcs_on: tcsOn,
      tcs_amt: tcsAmt,
      r_off_amt: rOffAmt,
      q_form_no: qFormNo,
      bill_amt: headerTotals.bill_amt,
      expenses,
      rate_rows: rateRows,
      bardana_rows: bardanaRows.filter((row) => row.item_name.trim()),
      ship_rows: shipRows.filter((row) => row.item_name.trim()),
      other_rows: otherRows.filter((row) => row.item_name.trim()),
      lines: lines.filter((line) => line.item_name.trim()),
    };
    const response = await api()?.save_invoice_entry?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.invoice_entry) applyRecord(response.invoice_entry);
    setStatus("Data has been Successfully Saved");
  }

  async function runPrint() {
    if (!documentId) {
      setError("Save the invoice before printing.");
      return;
    }
    const response = await api()?.print_document?.(documentId);
    if (!response?.ok) setError(response?.error ?? "Print failed.");
    else setStatus("Sent to printer.");
  }

  function runGenerateIrn() {
    setStatus("Generate IRN requires e-Invoice credentials (not configured).");
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
        if (index !== undefined) void openPicker("sale_ac", Number(index));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  async function confirmDelete() {
    if (!documentId) return;
    const response = await api()?.delete_invoice_entry?.(documentId);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    onExit();
  }

  function sideRowsForTab(): SideCategoryRow[] {
    if (sideCatTab === "bardana") return bardanaRows;
    if (sideCatTab === "ship") return shipRows;
    if (sideCatTab === "other") return otherRows;
    return sideLineRows;
  }

  function updateSideRow(index: number, patch: Partial<SideCategoryRow>) {
    const setter =
      sideCatTab === "bardana" ? setBardanaRows : sideCatTab === "ship" ? setShipRows : setOtherRows;
    setter((prev) => {
      const next = prev.map((row, i) => (i === index ? { ...row, ...patch } : row));
      const last = next[next.length - 1];
      if (last?.item_name.trim()) next.push(emptySideRow());
      return next;
    });
  }

  const sideEditable = sideCatTab === "bardana" || sideCatTab === "ship" || sideCatTab === "other";

  return (
    <>
      <form ref={formRef} className="invoice-entry-screen" onSubmit={(event) => void save(event)}>
        <header className="invoice-entry-title">{title}</header>
        <div className="invoice-entry-toolbar">
          <span className="invoice-entry-weekday">{weekday}</span>
          <span className="invoice-entry-user">User: {userName}</span>
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
          <button type="button" onClick={() => void runPrint()}>
            Print
          </button>
          <button type="button" onClick={runGenerateIrn}>
            Generate IRN
          </button>
          <button type="button" onClick={() => setExpenseOpen(true)}>
            Expenses
          </button>
          <button className="invoice-entry-recalc" type="button" onClick={recalculateAll}>
            Recalculate
          </button>
        </div>
        <div className="invoice-entry-header">
          <div className="invoice-entry-fields">
            <label>
              Date
              <input
                type={mode === "add" ? "date" : "text"}
                value={entryDate}
                onChange={(event) => setEntryDate(event.target.value)}
              />
            </label>
            <label>
              Book No.
              <input value={bookNo} onChange={(event) => setBookNo(event.target.value)} />
            </label>
            <label>
              Bill No.
              <input value={billNo} onChange={(event) => setBillNo(event.target.value)} />
            </label>
            <label className="wide">
              Party A/c
              <input
                value={partyName}
                onChange={(event) => setPartyName(event.target.value)}
                onFocus={() => void openPicker("party", -1, partyName)}
              />
            </label>
            <label className="wide">
              Dispatch
              <input value={dispatch} onChange={(event) => setDispatch(event.target.value)} />
            </label>
            <label>
              Due Days
              <input value={dueDays} onChange={(event) => setDueDays(event.target.value)} />
            </label>
            <label>
              Due Date
              <input value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            </label>
            <label className="wide">
              Broker A/c
              <input
                value={brokerName}
                onChange={(event) => setBrokerName(event.target.value)}
                onFocus={() => void openPicker("broker", -1, brokerName)}
              />
            </label>
            <label className="wide">
              Consignee
              <input value={consignee} onChange={(event) => setConsignee(event.target.value)} />
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
              Freight
              <input value={freight} onChange={(event) => setFreight(event.target.value)} />
            </label>
            <label className="wide">
              Transport
              <input value={transport} onChange={(event) => setTransport(event.target.value)} />
            </label>
            <label>
              Veh No.
              <input value={vehNo} onChange={(event) => setVehNo(event.target.value)} />
            </label>
            <label>
              E-Way No.
              <input value={ewayNo} onChange={(event) => setEwayNo(event.target.value)} />
            </label>
            <label>
              Driver Name
              <input value={driverName} onChange={(event) => setDriverName(event.target.value)} />
            </label>
            <label>
              Order No.
              <input value={orderNo} onChange={(event) => setOrderNo(event.target.value)} />
            </label>
            <label>
              Policy No
              <input value={policyNo} onChange={(event) => setPolicyNo(event.target.value)} />
            </label>
            <label className="wide">
              Dispatch A/c
              <input value={dispatchAc} onChange={(event) => setDispatchAc(event.target.value)} />
            </label>
            <label className="wide span-row">
              Remarks
              <input value={remarks} onChange={(event) => setRemarks(event.target.value)} />
            </label>
            <label>
              Cash/Credit
              <select value={cashCredit} onChange={(event) => setCashCredit(event.target.value)}>
                <option value="Credit">Credit</option>
                <option value="Cash">Cash</option>
              </select>
            </label>
            <label>
              Local/Central
              <select value={localCentral} onChange={(event) => setLocalCentral(event.target.value)}>
                <option value="Local">Local</option>
                <option value="Central">Central</option>
              </select>
            </label>
            <label>
              Sauda Mitti
              <input value={saudaMitti} onChange={(event) => setSaudaMitti(event.target.value)} />
            </label>
            <label>
              Consignee
              <select value={consigneeFlag} onChange={(event) => setConsigneeFlag(event.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
            <label>
              C/H Form
              <select value={chForm} onChange={(event) => setChForm(event.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
            <label>
              R/Off (N/B/A)
              <select value={roundOff} onChange={(event) => setRoundOff(event.target.value)}>
                <option value="N">N</option>
                <option value="B">B</option>
                <option value="A">A</option>
              </select>
            </label>
            <label>
              GST Type
              <select value={gstType} onChange={(event) => setGstType(event.target.value)}>
                <option value="U">U</option>
                <option value="R">R</option>
              </select>
            </label>
            <label>
              Scrap Bill
              <select value={scrapBill} onChange={(event) => setScrapBill(event.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
            <label>
              TCS R/Off
              <select value={tcsRoundOff} onChange={(event) => setTcsRoundOff(event.target.value)}>
                <option value="Y">Y</option>
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
              ROff Amt
              <input className="invoice-roff-amt" value={rOffAmt} onChange={(event) => setROffAmt(event.target.value)} />
            </label>
            <label>
              Q-FormNo
              <input value={qFormNo} onChange={(event) => setQFormNo(event.target.value)} />
            </label>
            <label>
              Bill Amt.
              <input readOnly className="invoice-bill-amt" value={headerTotals.bill_amt} />
            </label>
          </div>
          <div className="invoice-entry-side">
            <table className="invoice-rate-table">
              <thead>
                <tr>
                  <th>Rate</th>
                  <th>Gst On</th>
                  <th>CGST</th>
                  <th>SGST</th>
                  <th>IGST</th>
                  <th>Total Gst</th>
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
            <div className="invoice-side-tabs">
              <button
                className={sideCatTab === "rates" ? "active rates" : "rates"}
                type="button"
                onClick={() => setSideCatTab("rates")}
              >
                Rates
              </button>
              <button
                className={sideCatTab === "expense" ? "active expense" : "expense"}
                type="button"
                onClick={() => {
                  setSideCatTab("expense");
                  setExpenseOpen(true);
                }}
              >
                Expense
              </button>
              <button
                className={sideCatTab === "bardana" ? "active bardana" : "bardana"}
                type="button"
                onClick={() => setSideCatTab("bardana")}
              >
                Bardana
              </button>
              <button
                className={sideCatTab === "ship" ? "active ship" : "ship"}
                type="button"
                onClick={() => setSideCatTab("ship")}
              >
                Ship Fro
              </button>
              <button
                className={sideCatTab === "other" ? "active other" : "other"}
                type="button"
                onClick={() => setSideCatTab("other")}
              >
                Other
              </button>
            </div>
            <table className="invoice-side-grid">
              <thead>
                <tr>
                  <th>Item Name</th>
                  <th>Nugs</th>
                  <th>Weight</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {sideRowsForTab().map((row, index) => (
                  <tr key={`side-${sideCatTab}-${index}`}>
                    <td>
                      {sideEditable ? (
                        <input
                          value={row.item_name}
                          onChange={(event) => updateSideRow(index, { item_name: event.target.value })}
                        />
                      ) : (
                        row.item_name
                      )}
                    </td>
                    <td>
                      {sideEditable ? (
                        <input value={row.nugs} onChange={(event) => updateSideRow(index, { nugs: event.target.value })} />
                      ) : (
                        row.nugs
                      )}
                    </td>
                    <td>
                      {sideEditable ? (
                        <input
                          value={row.weight}
                          onChange={(event) => updateSideRow(index, { weight: event.target.value })}
                        />
                      ) : (
                        row.weight
                      )}
                    </td>
                    <td>
                      {sideEditable ? (
                        <input
                          value={row.amount}
                          onChange={(event) => updateSideRow(index, { amount: event.target.value })}
                        />
                      ) : (
                        row.amount
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="invoice-entry-grid-wrap" onKeyDown={handleGridEnter}>
          <table className="invoice-entry-grid">
            <thead>
              <tr>
                <th>#</th>
                <th>Item</th>
                <th>Desc</th>
                <th>Unit</th>
                <th>Sale A/c (F11)</th>
                <th>Qty</th>
                <th>Bharti</th>
                <th>Gr. Wt.</th>
                <th>Tare</th>
                <th>Shortage</th>
                <th>Net Wt.</th>
                <th>N/W</th>
                <th>Rate</th>
                <th>Amount</th>
                <th>Diff</th>
                <th>GstAdj</th>
                <th>GstAmt</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={`inv-${index}`} data-grid-row data-line-index={index}>
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
                    <input value={line.unit} onChange={(event) => updateLine(index, { unit: event.target.value })} />
                  </td>
                  <td>
                    <input
                      value={line.sale_ac}
                      onChange={(event) => updateLine(index, { sale_ac: event.target.value })}
                      onFocus={() => void openPicker("sale_ac", index)}
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
                      value={line.shortage}
                      onChange={(event) => updateLine(index, { shortage: event.target.value })}
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
                    <input value={line.diff} onChange={(event) => updateLine(index, { diff: event.target.value })} />
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
          <p className={`invoice-entry-status${error ? " invoice-entry-error" : ""}`}>{error || status}</p>
        )}
      </form>
      {picker && (
        <div className="invoice-picker" role="listbox">
          <ul>
            {picker.rows.map((row, index) => (
              <li key={`pick-${index}`}>
                <button type="button" onClick={() => applyPicker(row)}>
                  {picker.kind === "party"
                    ? String(row.name ?? "")
                    : picker.kind === "broker"
                      ? String(row.broker_name ?? row.name ?? "")
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
        title={`Invoice Expenses (${partyName || "Party"})`}
      />
      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={billNo || bookNo}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
