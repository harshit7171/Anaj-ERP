import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import DeleteConfirmModal from "../../components/DeleteConfirmModal";
import { useGridEnterNavigation } from "../../hooks/useGridEnterNavigation";
import {
  ddMmYyyyToIso,
  emptyKachiLine,
  isoToday,
  isoToDdMmYyyy,
  parseKachiLines,
  recalcLine,
  sumKachiTotals,
  withTrailingBlankLine,
  type KachiLine,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type KachiApi = {
  find_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  get_kachi_purchase?(args: Record<string, string>): Promise<ApiResult & { kachi_purchase?: Record<string, unknown> }>;
  save_kachi_purchase?(payload: Record<string, unknown>): Promise<ApiResult & { kachi_purchase?: Record<string, unknown> }>;
  delete_kachi_purchase?(document_id: string): Promise<ApiResult>;
  lookup_kachi_sellers?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_kachi_items?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_kachi_rates?(seller_party_id: string, commodity_id: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  suggest_kachi_po_no?(entry_date: string): Promise<ApiResult & { po_no?: string }>;
};

type PickerKind = "buyer" | "seller" | "item" | "rate";

type PickerState = {
  kind: PickerKind;
  lineIndex: number;
  rows: Record<string, unknown>[];
};

function api(): KachiApi | undefined {
  return window.pywebview?.api as unknown as KachiApi | undefined;
}

export default function KachiPurchaseScreen({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const screenTitle = mode === "add" ? "Kachi Purchase Add" : "Kachi Purchase Modify";
  const formRef = useRef<HTMLFormElement>(null);

  const [documentId, setDocumentId] = useState("");
  const [userName] = useState("USER");
  const [entryDate, setEntryDate] = useState(mode === "add" ? isoToday() : isoToDdMmYyyy(isoToday()));
  const [mandi, setMandi] = useState("KURUKHETRA");
  const [poNo, setPoNo] = useState("1");
  const [lockHours, setLockHours] = useState("24");
  const [buyerPartyId, setBuyerPartyId] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [lines, setLines] = useState<KachiLine[]>([emptyKachiLine("1")]);
  const [picker, setPicker] = useState<PickerState | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const totals = useMemo(() => sumKachiTotals(lines), [lines]);

  const handleGridEnter = useGridEnterNavigation(() => {
    setLines((prev) => withTrailingBlankLine(prev));
    return false;
  });

  useEffect(() => {
    if (mode !== "add") return;
    void api()?.suggest_kachi_po_no?.(entryDate).then((response) => {
      if (response?.ok && response.po_no) setPoNo(response.po_no);
    });
  }, [entryDate, mode]);

  function applyRecord(record: Record<string, unknown>) {
    setDocumentId(String(record.document_id ?? ""));
    const iso = String(record.entry_date ?? "");
    setEntryDate(mode === "add" ? iso : isoToDdMmYyyy(iso));
    setMandi(String(record.mandi ?? "KURUKHETRA"));
    setPoNo(String(record.po_no ?? ""));
    setLockHours(String(record.lock_hours ?? "24"));
    setBuyerPartyId(String(record.buyer_party_id ?? ""));
    setBuyerName(String(record.buyer_name ?? ""));
    setLines(parseKachiLines(record.lines));
    setStatus("Kachi purchase loaded.");
    setError("");
  }

  async function runFind() {
    const isoDate = ddMmYyyyToIso(entryDate);
    const response = await api()?.get_kachi_purchase?.({
      entry_date: isoDate,
      po_no: poNo.trim(),
      buyer_party_id: buyerPartyId,
    });
    if (!response?.ok || !response.kachi_purchase) {
      setError(response?.error ?? "Record not found.");
      return;
    }
    applyRecord(response.kachi_purchase);
  }

  function updateLine(index: number, patch: Partial<KachiLine>) {
    setLines((prev) => {
      const next = prev.map((line, i) => (i === index ? recalcLine({ ...line, ...patch }) : line));
      return withTrailingBlankLine(next);
    });
  }

  async function openPicker(kind: PickerKind, lineIndex: number, query = "") {
    const bridge = api();
    if (!bridge) return;
    if (kind === "buyer") {
      const response = await bridge.find_accounts?.(query || buyerName);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex: -1, rows: response.rows });
      return;
    }
    const line = lines[lineIndex];
    if (kind === "seller") {
      const response = await bridge.lookup_kachi_sellers?.(query || line.seller_name);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
      return;
    }
    if (kind === "item") {
      const response = await bridge.lookup_kachi_items?.(query || line.item_name);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
      return;
    }
    if (kind === "rate") {
      const response = await bridge.lookup_kachi_rates?.(line.seller_party_id, line.commodity_id);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
    }
  }

  function applyPicker(row: Record<string, unknown>) {
    if (!picker) return;
    if (picker.kind === "buyer") {
      setBuyerPartyId(String(row.party_id ?? ""));
      setBuyerName(String(row.name ?? row.account_name ?? ""));
      setPicker(null);
      return;
    }
    const index = picker.lineIndex;
    if (picker.kind === "seller") {
      updateLine(index, {
        seller_party_id: String(row.party_id ?? ""),
        seller_name: String(row.name ?? ""),
      });
    } else if (picker.kind === "item") {
      updateLine(index, {
        commodity_id: String(row.commodity_id ?? ""),
        item_name: String(row.item_name ?? ""),
      });
    } else if (picker.kind === "rate") {
      updateLine(index, {
        rate: String(row.rate ?? ""),
        weight: String(row.weight ?? lineWeightOrKeep(index, row)),
      });
    }
    setPicker(null);
  }

  function lineWeightOrKeep(index: number, row: Record<string, unknown>) {
    const existing = lines[index]?.weight;
    return existing && Number(existing) > 0 ? existing : String(row.weight ?? "");
  }

  async function save(postAndExit: boolean) {
    setError("");
    const isoDate = mode === "add" ? entryDate : ddMmYyyyToIso(entryDate);
    const payload = {
      document_id: documentId || undefined,
      user_name: userName,
      entry_date: isoDate,
      mandi,
      po_no: poNo.trim(),
      lock_hours: lockHours,
      buyer_party_id: buyerPartyId,
      buyer_name: buyerName,
      totals,
      lines: lines
        .filter((line) => line.seller_name.trim() || line.item_name.trim())
        .map((line) => ({
          ...line,
          bill_date: line.bill_date || (mode === "add" ? isoToDdMmYyyy(isoDate) : entryDate),
        })),
    };
    const response = await api()?.save_kachi_purchase?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.kachi_purchase) applyRecord(response.kachi_purchase);
    setStatus("Data has been Successfully Saved");
    if (postAndExit) onExit();
  }

  async function confirmDelete() {
    if (!documentId) return;
    const response = await api()?.delete_kachi_purchase?.(documentId);
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
        void save(false);
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

  return (
    <>
      <form
        ref={formRef}
        className="kachi-purchase-screen"
        data-kachi-purchase-form
        onSubmit={(event) => {
          event.preventDefault();
          void save(false);
        }}
      >
        <header className="kachi-purchase-title">{screenTitle}</header>
        <div className="kachi-purchase-toolbar">
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
          <button type="button" onClick={() => void save(true)}>
            Post
          </button>
          <span className="kachi-purchase-user">{userName}</span>
        </div>
        <div className="kachi-purchase-header">
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
            Mandi
            <input value={mandi} onChange={(event) => setMandi(event.target.value)} />
          </label>
          <label>
            P.O. No.
            <input value={poNo} onChange={(event) => setPoNo(event.target.value)} />
          </label>
          <label>
            Lock Hours
            <input value={lockHours} onChange={(event) => setLockHours(event.target.value)} />
          </label>
          <label className="kachi-purchase-buyer">
            Buyer
            <input
              value={buyerName}
              onChange={(event) => setBuyerName(event.target.value)}
              onFocus={() => void openPicker("buyer", -1, buyerName)}
            />
          </label>
          <div className="kachi-purchase-totals">
            <span>{totals.total_bags}</span>
            <span>{totals.total_weight}</span>
            <span>{totals.avg_rate}</span>
            <span>{totals.total_amount}</span>
          </div>
        </div>
        <div className="kachi-purchase-grid-wrap" onKeyDown={handleGridEnter}>
          <table className="kachi-purchase-grid">
            <thead>
              <tr>
                <th>#</th>
                <th>Seller</th>
                <th>Slip No</th>
                <th>Bill No</th>
                <th>Bill Date</th>
                <th>Item</th>
                <th>Bharti</th>
                <th>Bags</th>
                <th>Weight</th>
                <th>Rate</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={`kachi-${index}`} data-grid-row>
                  <td>{index + 1}</td>
                  <td>
                    <input
                      value={line.seller_name}
                      onChange={(event) => updateLine(index, { seller_name: event.target.value })}
                      onFocus={() => void openPicker("seller", index)}
                    />
                  </td>
                  <td>
                    <input
                      value={line.slip_no}
                      onChange={(event) => updateLine(index, { slip_no: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.bill_no}
                      onChange={(event) => updateLine(index, { bill_no: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.bill_date}
                      onChange={(event) => updateLine(index, { bill_date: event.target.value })}
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
                      value={line.bharti}
                      onChange={(event) => updateLine(index, { bharti: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.bags}
                      onChange={(event) => updateLine(index, { bags: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={line.weight}
                      onChange={(event) => updateLine(index, { weight: event.target.value })}
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
                    <input readOnly value={line.amount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(status || error) && (
          <p className={`kachi-purchase-status${error ? " kachi-purchase-error" : ""}`}>{error || status}</p>
        )}
      </form>
      {picker && (
        <div className="kachi-picker" role="listbox">
          <ul>
            {picker.rows.map((row, index) => (
              <li key={`pick-${index}`}>
                <button type="button" onClick={() => applyPicker(row)}>
                  {picker.kind === "buyer"
                    ? String(row.name ?? "")
                    : picker.kind === "seller"
                      ? String(row.name ?? "")
                      : picker.kind === "item"
                        ? String(row.item_name ?? "")
                        : `${String(row.rate ?? "")} · ${String(row.weight ?? "")}`}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <DeleteConfirmModal
        open={deleteOpen}
        recordLabel={`PO ${poNo}`}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
      />
    </>
  );
}
