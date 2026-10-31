import { FormEvent, useEffect, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import {
  ddMmYyyyToIso,
  emptyNoteLine,
  isoToday,
  isoToDdMmYyyy,
  parseNoteLines,
  withTrailingBlankLine,
  type NoteLine,
} from "./constants";

type NoteKind = "debit" | "credit";

type ApiResult = { ok: boolean; error?: string };

function apiPrefix(kind: NoteKind): "debit_note" | "credit_note" {
  return kind === "debit" ? "debit_note" : "credit_note";
}

type NoteApi = {
  get_debit_note_entry?(args: Record<string, string>): Promise<ApiResult & { debit_note_entry?: Record<string, unknown> }>;
  save_debit_note_entry?(payload: Record<string, unknown>): Promise<ApiResult & { debit_note_entry?: Record<string, unknown> }>;
  delete_debit_note_entry?(document_id: string): Promise<ApiResult>;
  lookup_debit_note_parties?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_debit_note_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_debit_note_items?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  next_debit_note_number?(): Promise<ApiResult & { document_number?: string }>;
  get_credit_note_entry?(args: Record<string, string>): Promise<ApiResult & { credit_note_entry?: Record<string, unknown> }>;
  save_credit_note_entry?(payload: Record<string, unknown>): Promise<ApiResult & { credit_note_entry?: Record<string, unknown> }>;
  delete_credit_note_entry?(document_id: string): Promise<ApiResult>;
  lookup_credit_note_parties?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_credit_note_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_credit_note_items?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  next_credit_note_number?(): Promise<ApiResult & { document_number?: string }>;
  print_voucher?(voucher_id: string): Promise<ApiResult>;
};

type PickerKind = "party" | "account" | "bardana_item" | "crop";

function bridge(): NoteApi | undefined {
  return window.pywebview?.api as unknown as NoteApi | undefined;
}

export default function NoteEntryScreen({
  kind,
  mode,
  onExit,
}: {
  kind: NoteKind;
  mode: "add" | "modify";
  onExit(): void;
}) {
  const label = kind === "debit" ? "Debit Note" : "Credit Note";
  const title = mode === "add" ? `${label} Add` : `${label} Modify`;
  const formRef = useRef<HTMLFormElement>(null);

  const [documentId, setDocumentId] = useState("");
  const [voucherId, setVoucherId] = useState("");
  const [noteNo, setNoteNo] = useState("");
  const [noteDate, setNoteDate] = useState(mode === "add" ? isoToday() : isoToDdMmYyyy(isoToday()));
  const [partyId, setPartyId] = useState("");
  const [partyName, setPartyName] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [reference1, setReference1] = useState("");
  const [reference2, setReference2] = useState("");
  const [reference3, setReference3] = useState("");
  const [bardanaQty, setBardanaQty] = useState("");
  const [bardanaItem, setBardanaItem] = useState("");
  const [cropName, setCropName] = useState("");
  const [lines, setLines] = useState<NoteLine[]>([emptyNoteLine()]);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [picker, setPicker] = useState<{ kind: PickerKind; lineIndex: number; rows: Record<string, unknown>[] } | null>(
    null,
  );
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const handleGridEnter = useGridEnterNavigation(() => {
    setLines((prev) => withTrailingBlankLine(prev));
    return false;
  });

  useEffect(() => {
    if (mode !== "add") return;
    const fn = kind === "debit" ? bridge()?.next_debit_note_number : bridge()?.next_credit_note_number;
    void fn?.().then((response) => {
      if (response?.ok && response.document_number) setNoteNo(response.document_number);
    });
  }, [kind, mode]);

  function applyRecord(record: Record<string, unknown>) {
    setDocumentId(String(record.document_id ?? ""));
    setVoucherId(String(record.voucher_id ?? ""));
    setNoteNo(String(record.note_no ?? ""));
    const iso = String(record.note_date ?? "");
    setNoteDate(mode === "add" ? iso : isoToDdMmYyyy(iso));
    setPartyId(String(record.party_id ?? ""));
    setPartyName(String(record.party_name ?? ""));
    setDueDate(String(record.due_date ?? ""));
    setReference1(String(record.reference_1 ?? ""));
    setReference2(String(record.reference_2 ?? ""));
    setReference3(String(record.reference_3 ?? ""));
    setBardanaQty(String(record.bardana_qty ?? ""));
    setBardanaItem(String(record.bardana_item ?? ""));
    setCropName(String(record.crop_name ?? ""));
    setLines(parseNoteLines(record.lines));
    setStatus(`${label} loaded.`);
    setError("");
  }

  async function runFind() {
    const isoDate = mode === "add" ? noteDate : ddMmYyyyToIso(noteDate);
    const args = {
      note_date: isoDate,
      party_id: partyId,
      note_no: noteNo.trim(),
    };
    const response =
      kind === "debit"
        ? await bridge()?.get_debit_note_entry?.(args)
        : await bridge()?.get_credit_note_entry?.(args);
    const key = kind === "debit" ? "debit_note_entry" : "credit_note_entry";
    const record = response?.[key as keyof typeof response] as Record<string, unknown> | undefined;
    if (!response?.ok || !record) {
      setError(response?.error ?? "Entry not found.");
      return;
    }
    applyRecord(record);
  }

  function updateLine(index: number, patch: Partial<NoteLine>) {
    setLines((prev) => withTrailingBlankLine(prev.map((line, i) => (i === index ? { ...line, ...patch } : line))));
  }

  async function openPicker(pickerKind: PickerKind, lineIndex: number, query = "") {
    const api = bridge();
    if (!api) return;
    if (pickerKind === "party") {
      const fn = kind === "debit" ? api.lookup_debit_note_parties : api.lookup_credit_note_parties;
      const response = await fn?.(query || partyName);
      if (response?.ok && response.rows) setPicker({ kind: pickerKind, lineIndex: -1, rows: response.rows });
      return;
    }
    if (pickerKind === "bardana_item" || pickerKind === "crop") {
      const fn = kind === "debit" ? api.lookup_debit_note_items : api.lookup_credit_note_items;
      const response = await fn?.(query || (pickerKind === "bardana_item" ? bardanaItem : cropName));
      if (response?.ok && response.rows) setPicker({ kind: pickerKind, lineIndex: -1, rows: response.rows });
      return;
    }
    const line = lines[lineIndex];
    const fn = kind === "debit" ? api.lookup_debit_note_accounts : api.lookup_credit_note_accounts;
    const response = await fn?.(query || line.account_name);
    if (response?.ok && response.rows) setPicker({ kind: pickerKind, lineIndex, rows: response.rows });
  }

  function applyPicker(row: Record<string, unknown>) {
    if (!picker) return;
    if (picker.kind === "party") {
      setPartyId(String(row.party_id ?? ""));
      setPartyName(String(row.name ?? ""));
    } else if (picker.kind === "bardana_item") {
      setBardanaItem(String(row.item_name ?? ""));
    } else if (picker.kind === "crop") {
      setCropName(String(row.item_name ?? ""));
    } else {
      updateLine(picker.lineIndex, {
        account_id: String(row.account_id ?? ""),
        account_name: String(row.account_name ?? ""),
      });
    }
    setPicker(null);
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const isoDate = mode === "add" ? noteDate : ddMmYyyyToIso(noteDate);
    const payload: Record<string, unknown> = {
      document_id: documentId || undefined,
      note_no: noteNo,
      note_date: isoDate,
      party_id: partyId,
      party_name: partyName,
      due_date: dueDate,
      reference_1: reference1,
      reference_2: reference2,
      reference_3: reference3,
      bardana_qty: bardanaQty,
      bardana_item: bardanaItem,
      crop_name: cropName,
      lines: lines.filter((line) => line.account_id && Number(line.amount) > 0),
    };
    const response =
      kind === "debit"
        ? await bridge()?.save_debit_note_entry?.(payload)
        : await bridge()?.save_credit_note_entry?.(payload);
    const key = kind === "debit" ? "debit_note_entry" : "credit_note_entry";
    const record = response?.[key as keyof typeof response] as Record<string, unknown> | undefined;
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (record) applyRecord(record);
    setStatus("Data has been Successfully Saved");
  }

  async function runPrint() {
    if (!voucherId) {
      setError("Save before print.");
      return;
    }
    const response = await bridge()?.print_voucher?.(voucherId);
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
    const response =
      kind === "debit"
        ? await bridge()?.delete_debit_note_entry?.(documentId)
        : await bridge()?.delete_credit_note_entry?.(documentId);
    setDeleteOpen(false);
    if (!response?.ok) {
      setError(response?.error ?? "Delete failed.");
      return;
    }
    onExit();
  }

  return (
    <>
      <form ref={formRef} className="simple-note-screen" onSubmit={(event) => void save(event)}>
        <header className="simple-note-title">{title}</header>
        <div className="simple-note-toolbar">
          <button type="button" onClick={() => void runFind()}>
            Find (F5)
          </button>
          <button type="submit">Save (F3)</button>
          <button type="button" onClick={onExit}>
            Cancel (F4)
          </button>
          {mode === "modify" && (
            <button className="delete-btn" disabled={!documentId} type="button" onClick={() => setDeleteOpen(true)}>
              Delete (F6)
            </button>
          )}
          <button type="button" onClick={() => void runPrint()}>
            Print
          </button>
        </div>
        <div className="simple-note-header">
          <label>
            {kind === "debit" ? "Debit Note No" : "Credit Note No"}
            <input value={noteNo} onChange={(event) => setNoteNo(event.target.value)} />
          </label>
          <label>
            {kind === "debit" ? "D. Note Date" : "C. Note Date"}
            <input
              type={mode === "add" ? "date" : "text"}
              value={noteDate}
              onChange={(event) => setNoteDate(event.target.value)}
            />
          </label>
          <label className="wide">
            Party Name
            <input
              value={partyName}
              onChange={(event) => setPartyName(event.target.value)}
              onFocus={() => void openPicker("party", -1, partyName)}
            />
          </label>
          <label>
            Due Date
            <input value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
          </label>
          <label className="wide">
            Reference - 1
            <input value={reference1} onChange={(event) => setReference1(event.target.value)} />
          </label>
          <label className="wide">
            Reference - 2
            <input value={reference2} onChange={(event) => setReference2(event.target.value)} />
          </label>
          <label className="wide">
            Reference - 3
            <input value={reference3} onChange={(event) => setReference3(event.target.value)} />
          </label>
          <label>
            Bardana Qty
            <input value={bardanaQty} onChange={(event) => setBardanaQty(event.target.value)} />
          </label>
          <label>
            Bardana Item
            <input
              value={bardanaItem}
              onChange={(event) => setBardanaItem(event.target.value)}
              onFocus={() => void openPicker("bardana_item", -1, bardanaItem)}
            />
          </label>
          <label>
            Crop Name
            <input
              value={cropName}
              onChange={(event) => setCropName(event.target.value)}
              onFocus={() => void openPicker("crop", -1, cropName)}
            />
          </label>
        </div>
        <div className="simple-note-grid-wrap" onKeyDown={handleGridEnter}>
          <table className="simple-note-grid">
            <thead>
              <tr>
                <th>#</th>
                <th>A/c Name</th>
                <th>Particulars</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={`${apiPrefix(kind)}-${index}`} data-grid-row data-line-index={index}>
                  <td>{index + 1}</td>
                  <td>
                    <input
                      value={line.account_name}
                      onChange={(event) => updateLine(index, { account_name: event.target.value })}
                      onFocus={() => void openPicker("account", index)}
                    />
                  </td>
                  <td>
                    <input
                      value={line.particulars}
                      onChange={(event) => updateLine(index, { particulars: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.amount}
                      onChange={(event) => updateLine(index, { amount: event.target.value })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(status || error) && (
          <p className={`simple-note-status${error ? " simple-note-error" : ""}`}>{error || status}</p>
        )}
      </form>
      {picker && (
        <div className="simple-note-picker" role="listbox">
          <ul>
            {picker.rows.map((row, index) => (
              <li key={`pick-${index}`}>
                <button type="button" onClick={() => applyPicker(row)}>
                  {picker.kind === "party"
                    ? String(row.name ?? "")
                    : picker.kind === "account"
                      ? String(row.account_name ?? "")
                      : String(row.item_name ?? "")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={noteNo}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
