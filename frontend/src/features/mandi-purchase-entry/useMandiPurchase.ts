import { FormEvent, useEffect, useMemo, useState } from "react";

import type { LiftingExpenseRow } from "../lifting-entry/constants";
import { emptyExpenseRow } from "../lifting-entry/constants";
import {
  buildItemSummary,
  ddMmYyyyToIso,
  emptyMandiLine,
  isoToday,
  isoToDdMmYyyy,
  parseMandiLines,
  recalcMandiLine,
  sumMandiTotals,
  weekdayLabel,
  withTrailingBlankLine,
  type BardanaTab,
  type MandiLine,
  type TransportTab,
} from "./constants";

type ApiResult = { ok: boolean; error?: string };

type MandiApi = {
  find_accounts?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  get_mandi_purchase_entry?(args: Record<string, string>): Promise<
    ApiResult & { mandi_purchase_entry?: Record<string, unknown> }
  >;
  save_mandi_purchase_entry?(payload: Record<string, unknown>): Promise<
    ApiResult & { mandi_purchase_entry?: Record<string, unknown> }
  >;
  delete_mandi_purchase_entry?(document_id: string): Promise<ApiResult>;
  lookup_mandi_parties?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_mandi_items?(query?: string): Promise<ApiResult & { rows?: Record<string, unknown>[] }>;
  lookup_mandi_line_rates?(line_party_id: string, commodity_id: string): Promise<
    ApiResult & { rows?: Record<string, unknown>[] }
  >;
  next_mandi_entry_number?(): Promise<ApiResult & { document_number?: string }>;
};

export type MandiPickerKind = "purchase_ac" | "party" | "item" | "rate";
export type MandiTabId = "items" | "transport" | "bardana";

function api(): MandiApi | undefined {
  return window.pywebview?.api as unknown as MandiApi | undefined;
}

export function useMandiPurchase({
  mode,
  onExit,
}: {
  mode: "add" | "modify";
  onExit(): void;
}) {
  const screenTitle = mode === "add" ? "Purchase Add" : "Purchase Modify";

  const [documentId, setDocumentId] = useState("");
  const [documentNumber, setDocumentNumber] = useState("");
  const [searchBillNo, setSearchBillNo] = useState("");
  const [userName] = useState("USER");
  const [entryDate, setEntryDate] = useState(mode === "add" ? isoToday() : isoToDdMmYyyy(isoToday()));
  const [cashCredit, setCashCredit] = useState("Credit");
  const [purchasePartyId, setPurchasePartyId] = useState("");
  const [purchasePartyName, setPurchasePartyName] = useState("");
  const [mandiCity, setMandiCity] = useState("KURUKHETRA");
  const [expMaster, setExpMaster] = useState("");
  const [broker, setBroker] = useState("");
  const [marketPaid, setMarketPaid] = useState("N");
  const [purType, setPurType] = useState("L");
  const [rcm, setRcm] = useState("N");
  const [gst, setGst] = useState("N");
  const [dueDate, setDueDate] = useState("");
  const [stockRcvd, setStockRcvd] = useState("N");
  const [tdsRate, setTdsRate] = useState("2.00");
  const [remarks, setRemarks] = useState("");
  const [lines, setLines] = useState<MandiLine[]>([emptyMandiLine()]);
  const [expenses, setExpenses] = useState<LiftingExpenseRow[]>([emptyExpenseRow()]);
  const [transport, setTransport] = useState<TransportTab>({
    transporter: "",
    vehicle_no: "",
    freight: "",
    remarks: "",
  });
  const [bardana, setBardana] = useState<BardanaTab>({
    bardana_type: "Jute",
    bags: "",
    remarks: "",
  });
  const [activeTab, setActiveTab] = useState<MandiTabId>("items");
  const [picker, setPicker] = useState<{ kind: MandiPickerKind; lineIndex: number; rows: Record<string, unknown>[] } | null>(
    null,
  );
  const [expenseOpen, setExpenseOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const totals = useMemo(() => sumMandiTotals(lines), [lines]);
  const itemSummary = useMemo(() => buildItemSummary(lines), [lines]);
  const weekday = useMemo(
    () => weekdayLabel(mode === "add" ? entryDate : ddMmYyyyToIso(entryDate)),
    [entryDate, mode],
  );

  useEffect(() => {
    if (mode !== "add") return;
    void api()?.next_mandi_entry_number?.().then((response) => {
      if (response?.ok && response.document_number) setDocumentNumber(response.document_number);
    });
  }, [mode]);

  /** Keep line amounts/TDS in sync when header TDS rate changes. */
  useEffect(() => {
    setLines((prev) => prev.map((line) => recalcMandiLine(line, tdsRate)));
  }, [tdsRate]);

  function applyRecord(record: Record<string, unknown>) {
    setDocumentId(String(record.document_id ?? ""));
    setDocumentNumber(String(record.document_number ?? ""));
    const iso = String(record.entry_date ?? "");
    setEntryDate(mode === "add" ? iso : isoToDdMmYyyy(iso));
    setCashCredit(String(record.cash_credit ?? "Credit"));
    setPurchasePartyId(String(record.purchase_party_id ?? ""));
    setPurchasePartyName(String(record.purchase_party_name ?? ""));
    setMandiCity(String(record.mandi_city ?? "KURUKHETRA"));
    setExpMaster(String(record.exp_master ?? ""));
    setBroker(String(record.broker ?? ""));
    setMarketPaid(String(record.market_paid ?? "N"));
    setPurType(String(record.pur_type ?? "L"));
    setRcm(String(record.rcm ?? "N"));
    setGst(String(record.gst ?? "N"));
    setDueDate(String(record.due_date ?? ""));
    setStockRcvd(String(record.stock_rcvd ?? "N"));
    setTdsRate(String(record.tds_rate ?? "2.00"));
    setRemarks(String(record.remarks ?? ""));
    setLines(parseMandiLines(record.lines));
    const rawExp = record.expenses;
    if (Array.isArray(rawExp) && rawExp.length) {
      setExpenses(
        rawExp.map((row) => {
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
    const tr = record.transport as TransportTab | undefined;
    if (tr) setTransport((prev) => ({ ...prev, ...tr }));
    const bd = record.bardana as BardanaTab | undefined;
    if (bd) setBardana((prev) => ({ ...prev, ...bd }));
    setStatus("Purchase entry loaded.");
    setError("");
  }

  async function runFind() {
    const isoDate = ddMmYyyyToIso(entryDate);
    const response = await api()?.get_mandi_purchase_entry?.({
      entry_date: isoDate,
      purchase_party_id: purchasePartyId,
      document_number: documentNumber.trim(),
      line_bill_no: searchBillNo.trim(),
    });
    if (!response?.ok || !response.mandi_purchase_entry) {
      setError(response?.error ?? "Entry not found.");
      return;
    }
    applyRecord(response.mandi_purchase_entry);
  }

  function updateLine(index: number, patch: Partial<MandiLine>) {
    setLines((prev) => {
      const next = prev.map((line, i) =>
        i === index ? recalcMandiLine({ ...line, ...patch }, tdsRate) : line,
      );
      return withTrailingBlankLine(next);
    });
  }

  async function openPicker(kind: MandiPickerKind, lineIndex: number, query = "") {
    const bridge = api();
    if (!bridge) return;
    if (kind === "purchase_ac") {
      const response = await bridge.find_accounts?.(query || purchasePartyName);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex: -1, rows: response.rows });
      return;
    }
    const line = lines[lineIndex];
    if (kind === "party") {
      const response = await bridge.lookup_mandi_parties?.(query || line.party_name);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
      return;
    }
    if (kind === "item") {
      const response = await bridge.lookup_mandi_items?.(query || line.item_name);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
      return;
    }
    if (kind === "rate") {
      const response = await bridge.lookup_mandi_line_rates?.(line.line_party_id, line.commodity_id);
      if (response?.ok && response.rows) setPicker({ kind, lineIndex, rows: response.rows });
    }
  }

  function applyPicker(row: Record<string, unknown>) {
    if (!picker) return;
    if (picker.kind === "purchase_ac") {
      setPurchasePartyId(String(row.party_id ?? ""));
      setPurchasePartyName(String(row.name ?? row.account_name ?? ""));
      setPicker(null);
      return;
    }
    const index = picker.lineIndex;
    if (picker.kind === "party") {
      updateLine(index, {
        line_party_id: String(row.party_id ?? ""),
        party_name: String(row.name ?? ""),
      });
    } else if (picker.kind === "item") {
      updateLine(index, {
        commodity_id: String(row.commodity_id ?? ""),
        item_name: String(row.item_name ?? ""),
        unit: String(row.unit ?? "Qtls"),
      });
    } else if (picker.kind === "rate") {
      updateLine(index, {
        rate: String(row.rate ?? ""),
        weight: lines[index]?.weight || String(row.weight ?? ""),
      });
    }
    setPicker(null);
  }

  function recalculateAll() {
    setLines((prev) => prev.map((line) => recalcMandiLine(line, tdsRate)));
    setStatus("Recalculated.");
  }

  function appendBlankLine() {
    setLines((prev) => withTrailingBlankLine(prev));
  }

  async function save(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const isoDate = mode === "add" ? entryDate : ddMmYyyyToIso(entryDate);
    const payload = {
      document_id: documentId || undefined,
      document_number: documentNumber,
      entry_date: isoDate,
      user_name: userName,
      cash_credit: cashCredit,
      purchase_party_id: purchasePartyId,
      purchase_party_name: purchasePartyName,
      mandi_city: mandiCity,
      exp_master: expMaster,
      broker,
      market_paid: marketPaid,
      pur_type: purType,
      rcm,
      gst,
      header_amount: totals.total_amount,
      due_date: dueDate,
      stock_rcvd: stockRcvd,
      tds_rate: tdsRate,
      remarks,
      expenses: expenses.filter((row) => row.particulars.trim()),
      item_summary: itemSummary,
      transport,
      bardana,
      totals,
      lines: lines.filter((line) => line.party_name.trim() || line.item_name.trim()),
    };
    const response = await api()?.save_mandi_purchase_entry?.(payload);
    if (!response?.ok) {
      setError(response?.error ?? "Save failed.");
      return;
    }
    if (response.mandi_purchase_entry) applyRecord(response.mandi_purchase_entry);
    setStatus("Data has been Successfully Saved");
  }

  async function confirmDelete() {
    if (!documentId) return;
    const response = await api()?.delete_mandi_purchase_entry?.(documentId);
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
      if (event.key === "F6" && mode === "modify" && documentId) {
        event.preventDefault();
        setDeleteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return {
    screenTitle,
    mode,
    onExit,
    documentId,
    documentNumber,
    setDocumentNumber,
    searchBillNo,
    setSearchBillNo,
    userName,
    entryDate,
    setEntryDate,
    cashCredit,
    setCashCredit,
    purchasePartyId,
    purchasePartyName,
    setPurchasePartyName,
    mandiCity,
    setMandiCity,
    expMaster,
    setExpMaster,
    broker,
    setBroker,
    marketPaid,
    setMarketPaid,
    purType,
    setPurType,
    rcm,
    setRcm,
    gst,
    setGst,
    dueDate,
    setDueDate,
    stockRcvd,
    setStockRcvd,
    tdsRate,
    setTdsRate,
    remarks,
    setRemarks,
    lines,
    updateLine,
    expenses,
    setExpenses,
    transport,
    setTransport,
    bardana,
    setBardana,
    activeTab,
    setActiveTab,
    picker,
    setPicker,
    expenseOpen,
    setExpenseOpen,
    deleteOpen,
    setDeleteOpen,
    status,
    error,
    totals,
    itemSummary,
    weekday,
    openPicker,
    applyPicker,
    recalculateAll,
    save,
    runFind,
    confirmDelete,
    appendBlankLine,
  };
}
