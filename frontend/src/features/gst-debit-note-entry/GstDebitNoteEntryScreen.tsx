import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import {
  buildRateSummary,
  ddMmYyyyToIso,
  emptyDebitLine,
  isoToday,
  isoToDdMmYyyy,
  parseDebitLines,
  recalcDebitLine,
  sumDebitHeaderTotals,
  weekdayLabel,
  withTrailingBlankLine,
  type GstDebitLine,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type DebitNoteApi = {
  get_gst_debit_note_entry?(args: Record<string, string>): Promise<
    ApiResult & { gst_debit_note_entry?: Record<string, unknown> }
  >;
  save_gst_debit_note_entry?(payload: Record<string, unknown>): Promise<
    ApiResult & { gst_debit_note_entry?: Record<string, unknown> }
  >;
  delete_gst_debit_note_entry?(document_id: string): Promise<ApiResult>;
  lookup_gst_debit_note_parties?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_gst_debit_note_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_gst_debit_note_items?(
    party_id: string,
    pur_sale?: string,
    query?: string,
  ): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_gst_debit_note_rates?(
    party_id: string,
    commodity_id: string,
    pur_sale?: string,
  ): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  fill_gst_debit_note_from_document?(
    party_id: string,
    doc_no: string,
    pur_sale?: string,
  ): Promise<ApiResult & { fill?: Record<string, unknown> }>;
  next_gst_debit_note_number?(): Promise<ApiResult & { document_number?: string }>;
  print_document?(document_id: string): Promise<ApiResult>;
};

type PickerKind = "party" | "line_ac" | "item" | "rate";

function api(): DebitNoteApi | undefined {
  return window.pywebview?.api as unknown as DebitNoteApi | undefined;
}

export default function GstDebitNoteEntryScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const title = mode === "add" ? "GST Debit Note Add" : "GST Debit Note Modify";
  const formRef = useRef<HTMLFormElement>(null);

  const [documentId, setDocumentId] = useState("");
  const [userName] = useState("USER");
  const [entryDate, setEntryDate] = useState(mode === "add" ? isoToday() : isoToDdMmYyyy(isoToday()));
  const [purSale, setPurSale] = useState("S");
  const [dNoteNo, setDNoteNo] = useState("");
  const [cashCredit, setCashCredit] = useState("R");
  const [localCentral, setLocalCentral] = useState("L");
  const [revCharges, setRevCharges] = useState("N");
  const [partyGstType, setPartyGstType] = useState("R");
  const [partyId, setPartyId] = useState("");
  const [partyName, setPartyName] = useState("");
  const [docNo, setDocNo] = useState("");
  const [docDate, setDocDate] = useState("");
  const [grNo, setGrNo] = useState("");
  const [grDate, setGrDate] = useState("");
  const [transport, setTransport] = useState("");
  const [vehNo, setVehNo] = useState("");
  const [driverName, setDriverName] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [agPurSale, setAgPurSale] = useState("P");
  const [stockEntry, setStockEntry] = useState("N");
  const [itemType, setItemType] = useState("C");
  const [addLess1, setAddLess1] = useState("");
  const [acAddLess1, setAcAddLess1] = useState("");
  const [addLess2, setAddLess2] = useState("");
  const [acAddLess2, setAcAddLess2] = useState("");
  const [addAny, setAddAny] = useState("");
  const [lessAny, setLessAny] = useState("");
  const [cropBichak, setCropBichak] = useState("");
  const [roundOff, setRoundOff] = useState("A");
  const [rOffAmt, setROffAmt] = useState("");
  const [refNo, setRefNo] = useState("");
  const [refDate, setRefDate] = useState("");
  const [reason, setReason] = useState("");
  const [remarks, setRemarks] = useState("");
  const [shipFrom, setShipFrom] = useState("");
  const [shipTo, setShipTo] = useState("");
  const [lines, setLines] = useState<GstDebitLine[]>([emptyDebitLine()]);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [shipModal, setShipModal] = useState<"from" | "to" | null>(null);
  const [picker, setPicker] = useState<{ kind: PickerKind; lineIndex: number; rows: Record<string, unknown>[] } | null>(
    null,
  );
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const rateRows = useMemo(() => buildRateSummary(lines), [lines]);
  const headerTotals = useMemo(() => sumDebitHeaderTotals(lines, rOffAmt), [lines, rOffAmt]);
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
    void api()?.next_gst_debit_note_number?.().then((response) => {
      if (response?.ok && response.document_number) setDNoteNo(response.document_number);
    });
  }, [mode]);

  function applyRecord(record: Record<string, unknown>) {
    setDocumentId(String(record.document_id ?? ""));
    setDNoteNo(String(record.d_note_no ?? record.document_number ?? ""));
    const iso = String(record.entry_date ?? "");
    setEntryDate(mode === "add" ? iso : isoToDdMmYyyy(iso));
    setPurSale(String(record.pur_sale ?? "S"));
    setCashCredit(String(record.cash_credit ?? "R"));
    setLocalCentral(String(record.local_central ?? "L"));
    setRevCharges(String(record.rev_charges ?? "N"));
    setPartyGstType(String(record.party_gst_type ?? "R"));
    setPartyId(String(record.party_id ?? ""));
    setPartyName(String(record.party_name ?? ""));
    setDocNo(String(record.doc_no ?? ""));
    setDocDate(String(record.doc_date ?? ""));
    setGrNo(String(record.gr_no ?? ""));
    setGrDate(String(record.gr_date ?? ""));
    setTransport(String(record.transport ?? ""));
    setVehNo(String(record.veh_no ?? ""));
    setDriverName(String(record.driver_name ?? ""));
    setDueDate(String(record.due_date ?? ""));
    setAgPurSale(String(record.ag_pur_sale ?? "P"));
    setStockEntry(String(record.stock_entry ?? "N"));
    setItemType(String(record.item_type ?? "C"));
    setAddLess1(String(record.add_less_1 ?? ""));
    setAcAddLess1(String(record.ac_add_less_1 ?? ""));
    setAddLess2(String(record.add_less_2 ?? ""));
    setAcAddLess2(String(record.ac_add_less_2 ?? ""));
    setAddAny(String(record.add_any ?? ""));
    setLessAny(String(record.less_any ?? ""));
    setCropBichak(String(record.crop_bichak ?? ""));
    setRoundOff(String(record.round_off ?? "A"));
    setROffAmt(String(record.r_off_amt ?? ""));
    setRefNo(String(record.ref_no ?? ""));
    setRefDate(String(record.ref_date ?? ""));
    setReason(String(record.reason ?? ""));
    setRemarks(String(record.remarks ?? ""));
    setShipFrom(String(record.ship_from ?? ""));
    setShipTo(String(record.ship_to ?? ""));
    setLines(parseDebitLines(record.lines));
    setStatus("GST debit note loaded.");
    setError("");
  }

  async function runFind() {
    const response = await api()?.get_gst_debit_note_entry?.({
      entry_date: ddMmYyyyToIso(entryDate),
      party_id: partyId,
      d_note_no: dNoteNo.trim(),
    });
    if (!response?.ok || !response.gst_debit_note_entry) {
      setError(response?.error ?? "Entry not found.");
      return;
    }
    applyRecord(response.gst_debit_note_entry);
  }

  function updateLine(index: number, patch: Partial<GstDebitLine>) {
    setLines((prev) => {
      const next = prev.map((line, i) => (i === index ? recalcDebitLine({ ...line, ...patch }) : line));
      return withTrailingBlankLine(next);
    });
  }

  async function openPicker(kind: PickerKind, lineIndex: number, query = "") {
    const bridge = api();
    if (!bridge) return;
    if (kind === "party") {
      const response = await bridge.lookup_gst_debit_note_parties?.(query || partyName);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex: -1, rows: response.rows });
      return;
    }
    const line = lines[lineIndex];
    if (kind === "line_ac") {
      const response = await bridge.lookup_gst_debit_note_accounts?.(query || line.line_account_name);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
      return;
    }
    if (kind === "item") {
      if (!partyId) {
        setError("Select Party A/c first.");
        return;
      }
      const response = await bridge.lookup_gst_debit_note_items?.(partyId, purSale, query || line.item_name);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
      return;
    }
    if (kind === "rate") {
      if (!partyId || !line.commodity_id) return;
      const response = await bridge.lookup_gst_debit_note_rates?.(partyId, line.commodity_id, purSale);
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
    if (picker.kind === "line_ac") {
      updateLine(index, {
        line_account_id: String(row.account_id ?? ""),
        line_account_name: String(row.account_name ?? ""),
      });
    } else if (picker.kind === "item") {
      updateLine(index, {
        commodity_id: String(row.commodity_id ?? ""),
        item_name: String(row.item_name ?? ""),
        item_desc: String(row.item_name ?? ""),
        hsn_code: String(row.hsn_code ?? ""),
      });
    } else if (picker.kind === "rate") {
      updateLine(index, {
        rate: String(row.rate ?? ""),
        qty: String(row.qty ?? lines[index]?.qty ?? ""),
      });
    }
    setPicker(null);
  }

  async function runFillData() {
    if (!partyId || !docNo.trim()) {
      setError("Party A/c and Doc No. are required for Fill Data.");
      return;
    }
    const response = await api()?.fill_gst_debit_note_from_document?.(partyId, docNo.trim(), purSale);
    if (!response?.ok || !response.fill) {
      setError(response?.error ?? "Could not fill from document.");
      return;
    }
    const fill = response.fill;
    if (fill.doc_date) setDocDate(String(fill.doc_date));
    if (fill.ref_no) setRefNo(String(fill.ref_no));
    setLines(parseDebitLines(fill.lines));
    setStatus("Filled from source document.");
    setError("");
  }

  function recalculateAll() {
    setLines((prev) => prev.map((line) => recalcDebitLine(line)));
    setStatus("Recalculated.");
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const isoDate = mode === "add" ? entryDate : ddMmYyyyToIso(entryDate);
    const payload: Record<string, unknown> = {
      document_id: documentId || undefined,
      document_number: dNoteNo,
      d_note_no: dNoteNo,
      entry_date: isoDate,
      user_name: userName,
      pur_sale: purSale,
      cash_credit: cashCredit,
      local_central: localCentral,
      rev_charges: revCharges,
      party_gst_type: partyGstType,
      party_id: partyId,
      party_name: partyName,
      doc_no: docNo,
      doc_date: docDate,
      gr_no: grNo,
      gr_date: grDate,
      transport,
      veh_no: vehNo,
      driver_name: driverName,
      due_date: dueDate,
      ag_pur_sale: agPurSale,
      stock_entry: stockEntry,
      item_type: itemType,
      add_less_1: addLess1,
      ac_add_less_1: acAddLess1,
      add_less_2: addLess2,
      ac_add_less_2: acAddLess2,
      add_any: addAny,
      less_any: lessAny,
      crop_bichak: cropBichak,
      gst_amt: headerTotals.gst_amt,
      round_off: roundOff,
      r_off_amt: rOffAmt,
      bill_amt: headerTotals.bill_amt,
      ref_no: refNo,
      ref_date: refDate,
      reason,
      remarks,
      ship_from: shipFrom,
      ship_to: shipTo,
      rate_rows: rateRows,
      lines: lines.filter((line) => line.item_name.trim()),
    };
    const response = await api()?.save_gst_debit_note_entry?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.gst_debit_note_entry) applyRecord(response.gst_debit_note_entry);
    setStatus("Data has been Successfully Saved");
  }

  async function runPrint() {
    if (!documentId) {
      setError("Save before print.");
      return;
    }
    const response = await api()?.print_document?.(documentId);
    if (!response?.ok) setError(response?.error ?? "Print failed.");
    else setStatus("Sent to printer.");
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
      if (event.key === "F5") {
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

  async function confirmDelete() {
    if (!documentId) return;
    const response = await api()?.delete_gst_debit_note_entry?.(documentId);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    onExit();
  }

  return (
    <>
      <form ref={formRef} className="gst-debit-note-screen" onSubmit={(event) => void save(event)}>
        <header className="gst-debit-note-title">{title}</header>
        <div className="gst-debit-note-toolbar">
          {mode === "modify" && (
            <button type="button" onClick={() => void runFind()}>
              Find (F5)
            </button>
          )}
          <span className="gst-debit-note-weekday">{weekday}</span>
          <span className="gst-debit-note-user">User: {userName}</span>
          <button type="submit">Save (F3)</button>
          <button type="button" onClick={onExit}>
            Cancel (F4)
          </button>
          <button className="fill-data" type="button" onClick={() => void runFillData()}>
            Fill Data
          </button>
          {mode === "modify" && (
            <button className="delete-btn" disabled={!documentId} type="button" onClick={() => setDeleteOpen(true)}>
              Delete (F6)
            </button>
          )}
          <button type="button" onClick={() => void runPrint()}>
            Print
          </button>
          <button type="button" onClick={() => setStatus("Generate IRN requires e-Invoice setup.")}>
            Generate IRN
          </button>
          <button type="button" onClick={() => setStatus("Generate EWay requires E-Way API setup.")}>
            Generate EWay
          </button>
          <button type="button" onClick={recalculateAll}>
            Recalculate
          </button>
        </div>
        <div className="gst-debit-note-body">
          <div className="gst-debit-note-fields">
            <label>
              Date
              <input
                type={mode === "add" ? "date" : "text"}
                value={entryDate}
                onChange={(event) => setEntryDate(event.target.value)}
              />
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
              Doc No.
              <input value={docNo} onChange={(event) => setDocNo(event.target.value)} />
            </label>
            <label>
              Doc Date
              <input value={docDate} onChange={(event) => setDocDate(event.target.value)} />
            </label>
            <label>
              Gr No.
              <input value={grNo} onChange={(event) => setGrNo(event.target.value)} />
            </label>
            <label>
              Gr Date
              <input value={grDate} onChange={(event) => setGrDate(event.target.value)} />
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
              Driver
              <input value={driverName} onChange={(event) => setDriverName(event.target.value)} />
            </label>
            <label>
              Add/Less - 1
              <input value={addLess1} onChange={(event) => setAddLess1(event.target.value)} />
            </label>
            <label>
              A/c For Add/Less - 1
              <input value={acAddLess1} onChange={(event) => setAcAddLess1(event.target.value)} />
            </label>
            <label>
              Add/Less - 2
              <input value={addLess2} onChange={(event) => setAddLess2(event.target.value)} />
            </label>
            <label>
              A/c For Add/Less - 2
              <input value={acAddLess2} onChange={(event) => setAcAddLess2(event.target.value)} />
            </label>
            <label>
              Add Any
              <input value={addAny} onChange={(event) => setAddAny(event.target.value)} />
            </label>
            <label>
              Less Any
              <input value={lessAny} onChange={(event) => setLessAny(event.target.value)} />
            </label>
            <label>
              Crop (Bichak)
              <input value={cropBichak} onChange={(event) => setCropBichak(event.target.value)} />
            </label>
            <label>
              GST Amount
              <input readOnly value={headerTotals.gst_amt} />
            </label>
            <label>
              R/Off
              <select value={roundOff} onChange={(event) => setRoundOff(event.target.value)}>
                <option value="N">N</option>
                <option value="B">B</option>
                <option value="A">A</option>
              </select>
            </label>
            <label>
              ROff Amt
              <input value={rOffAmt} onChange={(event) => setROffAmt(event.target.value)} />
            </label>
            <label>
              Bill Amount
              <input readOnly className="gst-debit-bill-amt" value={headerTotals.bill_amt} />
            </label>
            <label>
              Ref No.
              <input value={refNo} onChange={(event) => setRefNo(event.target.value)} />
            </label>
            <label>
              Ref Date
              <input value={refDate} onChange={(event) => setRefDate(event.target.value)} />
            </label>
            <label className="wide">
              Reason
              <input value={reason} onChange={(event) => setReason(event.target.value)} />
            </label>
            <label className="wide span-row">
              Remarks
              <input value={remarks} onChange={(event) => setRemarks(event.target.value)} />
            </label>
            <label>
              Purchase/Sale/Other
              <select value={purSale} onChange={(event) => setPurSale(event.target.value)}>
                <option value="P">P</option>
                <option value="S">S</option>
                <option value="O">O</option>
              </select>
            </label>
            <label>
              D. Note No.
              <input value={dNoteNo} onChange={(event) => setDNoteNo(event.target.value)} />
            </label>
            <label>
              Cash/Credit
              <select value={cashCredit} onChange={(event) => setCashCredit(event.target.value)}>
                <option value="R">R</option>
                <option value="C">C</option>
              </select>
            </label>
            <label>
              Local/Central
              <select value={localCentral} onChange={(event) => setLocalCentral(event.target.value)}>
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
            <label>
              Party GST Type
              <select value={partyGstType} onChange={(event) => setPartyGstType(event.target.value)}>
                <option value="R">R</option>
                <option value="U">U</option>
              </select>
            </label>
            <label>
              Due Date
              <input value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            </label>
            <label>
              Ag Pur/Sale
              <select value={agPurSale} onChange={(event) => setAgPurSale(event.target.value)}>
                <option value="P">P</option>
                <option value="S">S</option>
              </select>
            </label>
            <label>
              Stock Entry
              <select value={stockEntry} onChange={(event) => setStockEntry(event.target.value)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </label>
            <label>
              Item Type (Crop/Pest)
              <select value={itemType} onChange={(event) => setItemType(event.target.value)}>
                <option value="C">C</option>
                <option value="P">P</option>
              </select>
            </label>
            <div className="ship-buttons">
              <button type="button" onClick={() => setShipModal("from")}>
                Ship From
              </button>
              <button type="button" onClick={() => setShipModal("to")}>
                Ship To
              </button>
            </div>
          </div>
          <div className="gst-debit-note-side">
            <table className="gst-debit-rate-table">
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
          </div>
        </div>
        <div className="gst-debit-note-grid-wrap" onKeyDown={handleGridEnter}>
          <table className="gst-debit-note-grid">
            <thead>
              <tr>
                <th>#</th>
                <th>A/c</th>
                <th>Item</th>
                <th>Item Desc</th>
                <th>Bags</th>
                <th>Qty</th>
                <th>Rate</th>
                <th>Disc %</th>
                <th>Disc. Amt</th>
                <th>Amount</th>
                <th>HSN Code</th>
                <th>Gst Diff.</th>
                <th>Gst Amount</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={`gdn-${index}`} data-grid-row data-line-index={index}>
                  <td>{index + 1}</td>
                  <td>
                    <input
                      value={line.line_account_name}
                      onChange={(event) => updateLine(index, { line_account_name: event.target.value })}
                      onFocus={() => void openPicker("line_ac", index)}
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
                      value={line.item_desc}
                      onChange={(event) => updateLine(index, { item_desc: event.target.value })}
                    />
                  </td>
                  <td>
                    <input value={line.bags} onChange={(event) => updateLine(index, { bags: event.target.value })} />
                  </td>
                  <td>
                    <input value={line.qty} onChange={(event) => updateLine(index, { qty: event.target.value })} />
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
                      value={line.disc_pct}
                      onChange={(event) => updateLine(index, { disc_pct: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.disc_amt}
                      onChange={(event) => updateLine(index, { disc_amt: event.target.value })}
                    />
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
                      value={line.gst_diff}
                      onChange={(event) => updateLine(index, { gst_diff: event.target.value })}
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
          <p className={`gst-debit-note-status${error ? " gst-debit-note-error" : ""}`}>{error || status}</p>
        )}
      </form>
      {picker && (
        <div className="gst-debit-picker" role="listbox">
          <ul>
            {picker.rows.map((row, index) => (
              <li key={`pick-${index}`}>
                <button type="button" onClick={() => applyPicker(row)}>
                  {picker.kind === "party"
                    ? String(row.name ?? "")
                    : picker.kind === "line_ac"
                      ? String(row.account_name ?? "")
                      : picker.kind === "item"
                        ? String(row.item_name ?? "")
                        : `${String(row.rate ?? "")} / Qty ${String(row.qty ?? "")}`}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {shipModal && (
        <div className="gst-debit-ship-modal">
          <label>
            {shipModal === "from" ? "Ship From" : "Ship To"}
            <input
              value={shipModal === "from" ? shipFrom : shipTo}
              onChange={(event) =>
                shipModal === "from" ? setShipFrom(event.target.value) : setShipTo(event.target.value)
              }
            />
          </label>
          <button type="button" onClick={() => setShipModal(null)}>
            OK
          </button>
        </div>
      )}
      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={dNoteNo}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
